# filepath: /home/dathv2004/Documents/BKDN/Learning/PBL6/network_monitor/src/infra/network-capture/flow-processor/Dockerfile
# Flow Processor Dockerfile
#
# Mục đích: Process CSV files từ CICFlowMeter và stream to Kafka
# Lightweight service không cần privileged access

FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g 1001 processor && \
    useradd -r -u 1001 -g processor processor

# Create directories
RUN mkdir -p /output /processed /app /logs && \
    chown -R processor:processor /output /processed /app /logs

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY processor.py .

# Switch to non-root user
USER processor

# Environment variables with defaults
ENV INPUT_DIR=/output
ENV KAFKA_BROKERS=kafka:9092
ENV KAFKA_TOPIC=network-flows
ENV PROCESSED_FILES_DIR=/processed
ENV LOG_LEVEL=INFO
ENV PROCESSING_INTERVAL=10

# Expose volumes
VOLUME ["/output", "/processed", "/logs"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Wait for Kafka then start processor
CMD ["python", "processor.py"]