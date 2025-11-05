# CICFlowMeter Dockerfile
#
# Mục đích: Container để capture network traffic và extract features
# Tại sao Alpine: Lightweight, security-focused
# Tại sao không Ubuntu: Larger size, more attack surface
# Bản chất: tcpdump + CICFlowMeter + scheduling

FROM python:3.9-alpine

# Install dependencies
RUN apk add --no-cache \
    tcpdump \
    libpcap-dev \
    gcc \
    musl-dev \
    linux-headers \
    openjdk11-jre \
    && pip install --no-cache-dir \
        cicflowmeter \
        scapy \
        pandas \
        numpy \
    && rm -rf /var/cache/apk/*

# Create non-root user
RUN addgroup -g 1001 flowmeter && \
    adduser -D -s /bin/sh -u 1001 -G flowmeter flowmeter

# Create directories
RUN mkdir -p /output /tmp/pcap /app && \
    chown -R flowmeter:flowmeter /output /tmp/pcap /app

# Copy scripts
COPY capture.sh /app/capture.sh
COPY requirements.txt /app/requirements.txt

# Install Python requirements
RUN pip install --no-cache-dir -r /app/requirements.txt

# Make script executable
RUN chmod +x /app/capture.sh

# Set working directory
WORKDIR /app

# Switch to non-root user for security
USER flowmeter

# Expose volume for output
VOLUME ["/output", "/tmp/pcap"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD /app/capture.sh health

# Default command
CMD ["/app/capture.sh", "capture"]