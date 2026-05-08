# syntax=docker/dockerfile:1

##=====================================##
##             Build stage             ##
##=====================================##

FROM python:3.14.4-slim AS builder

# Inject UV for dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Set the working directory
WORKDIR /app

# Install Python dependencies
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Copy application code
COPY app/ ./app/

RUN python -m compileall -q ./app

##=====================================##
##             Final stage             ##
##=====================================##

FROM python:3.14.4-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libblas3 \
    liblapack3 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Create necessary data directories
RUN mkdir -p /app/ledger /app/db

# Transfer the virtual environment
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Declare volumes
VOLUME ["/app/ledger", "/app/db"]

# Copy the entrypoint script
COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["entrypoint.sh"]
CMD ["python", "-m", "app.main"]
