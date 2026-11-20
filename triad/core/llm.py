"""Unified LLM client interface supporting Gemini, OpenAI, and deterministic Mock providers."""

from __future__ import annotations

import json
import os
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

import httpx


class LLMResponse(BaseModel):
    """Normalized response from any LLM provider."""
    content: str
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int = 0
    total_tokens: int
    duration_seconds: float = 0.0
    raw_response: Optional[Dict[str, Any]] = None


class BaseLLMProvider(ABC):
    """Abstract base provider for LLM inferences."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Execute a completion request."""
        pass


class MockLLMProvider(BaseLLMProvider):
    """Deterministic, high-speed mock provider for offline testing and reproducible benchmarks."""

    def __init__(self, predefined_responses: Optional[Dict[str, str]] = None, tokens_per_char: float = 0.25):
        self.predefined_responses = predefined_responses or {}
        self.tokens_per_char = tokens_per_char
        self._counter = 0

    def register_response(self, pattern: str, response: str) -> None:
        self.predefined_responses[pattern] = response

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> LLMResponse:
        t0 = time.perf_counter()
        self._counter += 1

        # Match regex or keyword in prompt or system prompt
        matched_content: Optional[str] = None
        full_text = f"{system_prompt or ''}\n{prompt}"
        for pat, resp in self.predefined_responses.items():
            if pat in full_text or re.search(pat, full_text, re.IGNORECASE):
                matched_content = resp
                break

        if matched_content is None:
            if "Decompose this workload" in prompt or "Workload Name:" in prompt:
                matched_content = json.dumps({
                    "slices": [
                        {
                            "slice_id": "slice_01_core",
                            "title": "Core Module Implementation",
                            "description": "Implement core business logic",
                            "target_files": ["core_module.py"],
                            "contract": {
                                "module_path": "core_module.py",
                                "exported_symbols": ["execute_process"],
                                "signatures": {"execute_process": "def execute_process(item_id: str) -> bool"},
                                "invariants": ["Returns True on valid item"]
                            },
                            "acceptance_tests": {
                                "test_core.py": "from core_module import execute_process\ndef test_exec(): assert execute_process('item_1')"
                            },
                            "dependencies": []
                        },
                        {
                            "slice_id": "slice_02_handler",
                            "title": "Handler Service Implementation",
                            "description": "Implement request handler logic",
                            "target_files": ["handler_service.py"],
                            "contract": {
                                "module_path": "handler_service.py",
                                "exported_symbols": ["handle_event"],
                                "signatures": {"handle_event": "def handle_event(payload: dict) -> dict"},
                                "invariants": ["Echoes back event status"]
                            },
                            "acceptance_tests": {
                                "test_handler.py": "from handler_service import handle_event\ndef test_handler(): res = handle_event({'k': 'v'}); assert res['status'] == 'ok'"
                            },
                            "dependencies": []
                        }
                    ]
                })
            elif "Task Slice:" in prompt:
                # Extract target file and symbol if possible
                target_file = "module.py"
                if "Target Files:" in prompt:
                    m = re.search(r"Target Files:\s*\[['\"]([^'\"]+)['\"]", prompt)
                    if m:
                        target_file = m.group(1)
                
                # Check exported symbols
                code_lines = []
                if "execute_process" in prompt:
                    code_lines.append("def execute_process(item_id: str) -> bool:\n    return len(item_id) > 0\n")
                elif "handle_event" in prompt:
                    code_lines.append("def handle_event(payload: dict) -> dict:\n    return {'status': 'ok', 'data': payload}\n")
                else:
                    code_lines.append(f"# Auto-generated implementation for {target_file}\ndef default_handler():\n    return True\n")
                
                matched_content = json.dumps({
                    "files": {target_file: "\n".join(code_lines)},
                    "summary": f"Generated default implementation for {target_file}"
                })
            elif json_mode:
                matched_content = json.dumps({"status": "mock_success", "index": self._counter})
            else:
                matched_content = f"Mock response for query #{self._counter}"

        prompt_tokens = max(10, int(len(full_text) * self.tokens_per_char))
        completion_tokens = max(5, int(len(matched_content) * self.tokens_per_char))
        duration = time.perf_counter() - t0

        return LLMResponse(
            content=matched_content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=0,
            total_tokens=prompt_tokens + completion_tokens,
            duration_seconds=duration,
        )


class GeminiProvider(BaseLLMProvider):
    """Direct asynchronous Google Gemini REST API provider with token tracking."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required for GeminiProvider.")
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> LLMResponse:
        t0 = time.perf_counter()

        contents: List[Dict[str, Any]] = [
            {"role": "user", "parts": [{"text": prompt}]}
        ]

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
            }
        }

        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}]
            }

        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        headers = {"Content-Type": "application/json"}
        params = {"key": self.api_key}

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(self.base_url, params=params, json=payload, headers=headers)
            duration = time.perf_counter() - t0

            if resp.status_code != 200:
                raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text}")

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError(f"No candidate in Gemini response: {data}")

            parts = candidates[0].get("content", {}).get("parts", [])
            content_text = "".join(p.get("text", "") for p in parts)

            usage = data.get("usageMetadata", {})
            prompt_tokens = usage.get("promptTokenCount", int(len(prompt) / 4))
            completion_tokens = usage.get("candidatesTokenCount", int(len(content_text) / 4))
            cached_tokens = usage.get("cachedContentTokenCount", 0)
            total_tokens = usage.get("totalTokenCount", prompt_tokens + completion_tokens)

            return LLMResponse(
                content=content_text,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_tokens=cached_tokens,
                total_tokens=total_tokens,
                duration_seconds=duration,
                raw_response=data,
            )


class OpenAIProvider(BaseLLMProvider):
    """Direct asynchronous OpenAI REST API provider with token tracking."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required for OpenAIProvider.")
        self.model = model
        self.base_url = "https://api.openai.com/v1/chat/completions"

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> LLMResponse:
        t0 = time.perf_counter()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(self.base_url, json=payload, headers=headers)
            duration = time.perf_counter() - t0

            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI API error ({resp.status_code}): {resp.text}")

            data = resp.json()
            content_text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            prompt_cached = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)

            return LLMResponse(
                content=content_text,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_tokens=prompt_cached,
                total_tokens=usage.get("total_tokens", prompt_tokens + completion_tokens),
                duration_seconds=duration,
                raw_response=data,
            )


class OpenAICompatibleProvider(BaseLLMProvider):
    """
    OpenAI-compatible REST API provider for local models (Ollama, vLLM, LMStudio, LocalAI).
    Allows running Triad Swarm 100% locally with 0 API costs and complete data privacy.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: str = "qwen2.5-coder:7b",
    ):
        raw_base = (
            base_url
            or os.environ.get("OPENAI_BASE_URL")
            or os.environ.get("OLLAMA_HOST")
            or "http://localhost:11434/v1"
        ).rstrip("/")
        if not raw_base.endswith("/chat/completions"):
            self.endpoint = f"{raw_base}/chat/completions"
        else:
            self.endpoint = raw_base
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "local-token")
        self.model = model

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> LLMResponse:
        t0 = time.perf_counter()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(self.endpoint, json=payload, headers=headers)
            duration = time.perf_counter() - t0

            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI-compatible endpoint error ({resp.status_code}): {resp.text}")

            data = resp.json()
            content_text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", max(1, int(len(prompt) / 4)))
            completion_tokens = usage.get("completion_tokens", max(1, int(len(content_text) / 4)))

            return LLMResponse(
                content=content_text,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_tokens=0,
                total_tokens=usage.get("total_tokens", prompt_tokens + completion_tokens),
                duration_seconds=duration,
                raw_response=data,
            )


class CachedLLMProvider(BaseLLMProvider):
    """
    Transparent prompt cache wrapper around any BaseLLMProvider.
    Yields 0 network requests and sub-millisecond responses on exact semantic hits.
    """

    def __init__(self, provider: BaseLLMProvider, cache: Any = None):
        from triad.core.cache import PromptCacheManager
        self.provider = provider
        self.cache = cache if cache is not None else PromptCacheManager()
        self.model = getattr(provider, "model", "default")

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> LLMResponse:
        key = self.cache.compute_key(
            prompt=prompt,
            system_prompt=system_prompt,
            json_mode=json_mode,
            model=self.model,
            temperature=temperature,
        )
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        resp = await self.provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            json_mode=json_mode,
            temperature=temperature,
        )
        self.cache.put(key, resp)
        return resp

    def __getattr__(self, name: str) -> Any:
        return getattr(self.provider, name)


def get_llm_provider(
    provider_name: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    enable_cache: bool = False,
    cache: Any = None,
    base_url: Optional[str] = None,
) -> BaseLLMProvider:
    """Factory helper to obtain an LLM provider based on config or env."""
    choice = provider_name or os.environ.get("TRIAD_LLM_PROVIDER", "").lower()

    if choice == "mock":
        provider: BaseLLMProvider = MockLLMProvider()
    elif choice in ("ollama", "local", "vllm", "openai-compatible"):
        provider = OpenAICompatibleProvider(
            base_url=base_url,
            api_key=api_key,
            model=model or "qwen2.5-coder:7b",
        )
    elif (choice == "gemini" or not choice) and (api_key or os.environ.get("GEMINI_API_KEY")):
        provider = GeminiProvider(api_key=api_key, model=model or os.environ.get("GEMINI_MODEL", "gemini-3.8-flash"))
    elif (choice == "openai" or not choice) and (api_key or os.environ.get("OPENAI_API_KEY")):
        provider = OpenAIProvider(api_key=api_key, model=model or "gpt-4o-mini")
    else:
        provider = MockLLMProvider()

    if enable_cache:
        return CachedLLMProvider(provider, cache=cache)
    return provider


def populate_mock_telemetry_defaults(mock: MockLLMProvider) -> None:
    """Register high-fidelity mock implementations for reproducible offline telemetry benchmarks."""
    architect_json = json.dumps({
        "slices": [
            {
                "slice_id": "slice_storage",
                "title": "Time-Series Ring Buffer Storage",
                "description": "Implement InMemoryRingBuffer with append and query_range",
                "target_files": ["telemetry/storage.py"],
                "contract": {
                    "module_path": "telemetry/storage.py",
                    "exported_symbols": ["InMemoryRingBuffer"],
                    "signatures": {
                        "append": "def append(self, timestamp: float, value: float) -> None",
                        "query_range": "def query_range(self, start_ts: float, end_ts: float) -> list"
                    },
                    "invariants": ["Points must remain ordered by timestamp"]
                },
                "acceptance_tests": {
                    "tests/test_storage.py": (
                        "from telemetry.storage import InMemoryRingBuffer\n"
                        "def test_buffer():\n"
                        "    buf = InMemoryRingBuffer(capacity=10)\n"
                        "    buf.append(1.0, 10.0)\n"
                        "    buf.append(2.0, 20.0)\n"
                        "    res = buf.query_range(0.0, 3.0)\n"
                        "    assert len(res) == 2\n"
                    )
                },
                "dependencies": []
            },
            {
                "slice_id": "slice_stats",
                "title": "Windowed Statistics Engine",
                "description": "Implement compute_percentiles and compute_mean",
                "target_files": ["telemetry/statistics.py"],
                "contract": {
                    "module_path": "telemetry/statistics.py",
                    "exported_symbols": ["compute_percentiles", "compute_mean"],
                    "signatures": {
                        "compute_percentiles": "def compute_percentiles(values: list, percentiles: list) -> dict",
                        "compute_mean": "def compute_mean(values: list) -> float"
                    },
                    "invariants": ["Mean of empty list is 0.0"]
                },
                "acceptance_tests": {
                    "tests/test_stats.py": (
                        "from telemetry.statistics import compute_percentiles, compute_mean\n"
                        "def test_stats():\n"
                        "    vals = [10.0, 20.0, 30.0, 40.0, 50.0]\n"
                        "    assert compute_mean(vals) == 30.0\n"
                        "    pcts = compute_percentiles(vals, [50, 90])\n"
                        "    assert 50 in pcts\n"
                    )
                },
                "dependencies": []
            },
            {
                "slice_id": "slice_alerts",
                "title": "Threshold Alert Evaluator",
                "description": "Implement AlertRule and evaluate_alerts",
                "target_files": ["telemetry/alerts.py"],
                "contract": {
                    "module_path": "telemetry/alerts.py",
                    "exported_symbols": ["AlertRule", "evaluate_alerts"],
                    "signatures": {
                        "evaluate_alerts": "def evaluate_alerts(rules: list, current_value: float) -> list"
                    },
                    "invariants": ["Returns triggered rule names"]
                },
                "acceptance_tests": {
                    "tests/test_alerts.py": (
                        "from telemetry.alerts import AlertRule, evaluate_alerts\n"
                        "def test_alerts():\n"
                        "    rule = AlertRule(name='HighLatency', threshold=100.0)\n"
                        "    triggered = evaluate_alerts([rule], 150.0)\n"
                        "    assert 'HighLatency' in triggered\n"
                    )
                },
                "dependencies": []
            },
            {
                "slice_id": "slice_exporter",
                "title": "Dashboard Exporter Payload Formatter",
                "description": "Implement format_dashboard_payload",
                "target_files": ["telemetry/exporter.py"],
                "contract": {
                    "module_path": "telemetry/exporter.py",
                    "exported_symbols": ["format_dashboard_payload"],
                    "signatures": {
                        "format_dashboard_payload": "def format_dashboard_payload(metric_name: str, stats: dict, alerts: list) -> dict"
                    },
                    "invariants": ["Must contain metric, stats, alerts, and timestamp keys"]
                },
                "acceptance_tests": {
                    "tests/test_exporter.py": (
                        "from telemetry.exporter import format_dashboard_payload\n"
                        "def test_exporter():\n"
                        "    p = format_dashboard_payload('cpu_load', {'mean': 45.2}, ['Warning'])\n"
                        "    assert p['metric'] == 'cpu_load'\n"
                        "    assert p['stats']['mean'] == 45.2\n"
                    )
                },
                "dependencies": []
            }
        ]
    })
    mock.register_response("Telemetry & Analytics", architect_json)
    mock.register_response("High-Throughput", architect_json)

    storage_code = json.dumps({
        "files": {
            "telemetry/storage.py": (
                "class InMemoryRingBuffer:\n"
                "    def __init__(self, capacity: int = 1000):\n"
                "        self.capacity = capacity\n"
                "        self.buffer = []\n\n"
                "    def append(self, timestamp: float, value: float) -> None:\n"
                "        if len(self.buffer) >= self.capacity:\n"
                "            self.buffer.pop(0)\n"
                "        self.buffer.append((timestamp, value))\n\n"
                "    def query_range(self, start_ts: float, end_ts: float) -> list:\n"
                "        return [val for ts, val in self.buffer if start_ts <= ts <= end_ts]\n"
            )
        }
    })
    mock.register_response("slice_storage", storage_code)

    stats_code = json.dumps({
        "files": {
            "telemetry/statistics.py": (
                "def compute_mean(values: list) -> float:\n"
                "    if not values:\n"
                "        return 0.0\n"
                "    return sum(values) / len(values)\n\n"
                "def compute_percentiles(values: list, percentiles: list) -> dict:\n"
                "    if not values:\n"
                "        return {p: 0.0 for p in percentiles}\n"
                "    sorted_v = sorted(values)\n"
                "    res = {}\n"
                "    for p in percentiles:\n"
                "        idx = int((p / 100.0) * len(sorted_v))\n"
                "        idx = min(idx, len(sorted_v) - 1)\n"
                "        res[p] = sorted_v[idx]\n"
                "    return res\n"
            )
        }
    })
    mock.register_response("slice_stats", stats_code)

    alerts_code = json.dumps({
        "files": {
            "telemetry/alerts.py": (
                "class AlertRule:\n"
                "    def __init__(self, name: str, threshold: float):\n"
                "        self.name = name\n"
                "        self.threshold = threshold\n\n"
                "def evaluate_alerts(rules: list, current_value: float) -> list:\n"
                "    triggered = []\n"
                "    for r in rules:\n"
                "        if current_value >= r.threshold:\n"
                "            triggered.append(r.name)\n"
                "    return triggered\n"
            )
        }
    })
    mock.register_response("slice_alerts", alerts_code)

    exporter_code = json.dumps({
        "files": {
            "telemetry/exporter.py": (
                "import time\n\n"
                "def format_dashboard_payload(metric_name: str, stats: dict, alerts: list) -> dict:\n"
                "    return {\n"
                "        'metric': metric_name,\n"
                "        'stats': stats,\n"
                "        'alerts': alerts,\n"
                "        'timestamp': time.time(),\n"
                "    }\n"
            )
        }
    })
    mock.register_response("slice_exporter", exporter_code)
