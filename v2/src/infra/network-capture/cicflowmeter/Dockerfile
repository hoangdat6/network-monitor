FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tcpdump \
    inotify-tools \
    net-tools \
    iproute2 \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Create directories with proper permissions
RUN mkdir -p /output /tmp/pcap /app /logs && \
    chmod 777 /output /tmp/pcap /logs

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY capture.sh ./
RUN chmod +x capture.sh

# Environment variables with defaults
ENV INTERFACE=wlp1s0
ENV CAPTURE_INTERVAL=60
ENV OUTPUT_DIR=/output
ENV KAFKA_TOPIC=network-flows
ENV LOG_LEVEL=INFO

# Expose volumes
VOLUME ["/output", "/tmp/pcap", "/logs"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD ./capture.sh health || exit 1

# Run as root for packet capture (required for tcpdump)
USER root

# Default command
CMD ["./capture.sh", "start"]