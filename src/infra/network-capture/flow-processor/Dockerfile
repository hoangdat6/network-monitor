# filepath: /home/dathv2004/Documents/BKDN/Learning/PBL6/network_monitor/src/infra/network-capture/flow-processor/Dockerfile
# Build stage
FROM python:3.12-slim as builder

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Create directories
RUN mkdir -p /output /processed /app /logs

# Set working directory
WORKDIR /app

# Copy only the installed packages from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application files
COPY processor.py .
COPY ip_filter_config.yaml .

# Expose volumes
VOLUME ["/output", "/processed", "/logs"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Wait for Kafka then start processor
CMD ["python", "processor.py"]