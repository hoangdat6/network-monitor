# Build stage
FROM python:3.12-slim as builder

WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --user --no-cache-dir --timeout=300 -r requirements.txt || \
    pip install --user --no-cache-dir --timeout=300 -r requirements.txt

# Runtime stage
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tcpdump \
    iproute2 \
    net-tools \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Create directories with proper permissions
RUN mkdir -p /output /app && chmod 777 /output

# Set working directory
WORKDIR /app

# Copy only the installed packages from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application
COPY capture_realtime.py ./

# Expose volumes
VOLUME ["/output"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD test -f /output/health || exit 1

# Run as root for packet capture
USER root

# Default command
CMD ["python3", "-u", "capture_realtime.py"]
