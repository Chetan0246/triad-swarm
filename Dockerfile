FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for ultra-fast packaging
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project definition and lockfile
COPY pyproject.toml uv.lock README.md /app/

# Install dependencies into virtual environment
RUN uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install --no-cache -e .

# Copy application source
COPY triad /app/triad
COPY docs /app/docs
COPY examples /app/examples

ENV PATH="/opt/venv/bin:$PATH"

ENTRYPOINT ["triad"]
CMD ["--help"]
