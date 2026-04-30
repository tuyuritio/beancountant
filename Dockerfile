## Build stage

FROM python:3.14.4-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
	build-essential \
	bison \
	flex \
	libsqlite3-dev \
    libblas3 \
    liblapack3 \
	&& rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

## Final stage

FROM python:3.14.4-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gosu \
    libsqlite3-0 \
    libblas3 \
    liblapack3 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN groupadd -r -g 1000 appuser \
    && useradd -r -u 1000 -g appuser appuser

# Set the working directory
WORKDIR /app

# Create necessary data directories
RUN mkdir -p /app/ledger /app/db

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code and set ownership
COPY . /app
RUN chown -R appuser:appuser /app

# Declare volumes
VOLUME /app/ledger
VOLUME /app/db

# Copy the entrypoint script
COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["entrypoint.sh"]
CMD ["python", "-m", "app.main"]
