# Multi-stage build for ARM64 Raspberry Pi deployment
FROM --platform=linux/arm64 python:3.13-slim as builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    inkscape \
    imagemagick \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock ./
COPY mqtt_thermometer/ ./mqtt_thermometer/
COPY scripts/ ./scripts/

# Create virtual environment and install dependencies
RUN uv sync --no-dev

# Generate favicons (cottage version)
RUN uv run ./scripts/create-favicons-cottage.sh

# Build the package
RUN uv build

# Runtime stage
FROM --platform=linux/arm64 python:3.13-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Create app user
RUN useradd --create-home --shell /bin/bash app

# Set working directory
WORKDIR /app

# Copy built package from builder stage
COPY --from=builder /app/dist/*.whl /tmp/

# Install the application using uv
RUN uv pip install --system /tmp/*.whl uvicorn && \
    rm /tmp/*.whl

# Create necessary directories
RUN mkdir -p /app/data /app/config && \
    chown -R app:app /app

# Switch to app user
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/temperatures')" || exit 1

# Default command
CMD ["uvicorn", "mqtt_thermometer.service:app", "--host", "0.0.0.0", "--port", "8000"]
