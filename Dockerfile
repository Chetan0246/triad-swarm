# Multi-stage production Dockerfile for Triad Swarm
# Stage 1: Build virtual environment with uv
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

COPY pyproject.toml uv.lock README.md /build/
RUN uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install --no-cache -e .

# Stage 2: Hardened, Non-Root Production Runtime
FROM python:3.12-slim AS runner

WORKDIR /app

# Install minimal runtime utilities (curl for healthchecks, git)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Security: Create unprivileged system user and group
RUN groupadd -g 10001 triad && \
    useradd -u 10001 -g triad -m -s /bin/bash triad

# Copy virtual environment and app code
COPY --from=builder /opt/venv /opt/venv
COPY --chown=triad:triad triad /app/triad
COPY --chown=triad:triad docs /app/docs
COPY --chown=triad:triad examples /app/examples
COPY --chown=triad:triad pyproject.toml README.md /app/

# Create persistent runtime data directories with triad permissions
RUN mkdir -p /app/out /app/.triad_cache && \
    chown -R triad:triad /app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED="1" \
    PYTHONDONTWRITEBYTECODE="1" \
    TRIAD_LOG_FORMAT="json"

USER triad:triad

EXPOSE 8000

# Container healthcheck querying liveness endpoint
HEALTHCHECK --interval=15s --timeout=4s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

ENTRYPOINT ["triad"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000", "--log-format", "json"]
