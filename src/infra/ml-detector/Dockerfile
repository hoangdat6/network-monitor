# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install dependencies in user space
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Copy only the installed packages from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy detector code and rules
COPY ml_detector.py .
COPY detection_rules.yaml .

# Copy models (will be mounted from volume)
RUN mkdir -p /models

# Clean up
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000')" || exit 1

CMD ["python", "-u", "ml_detector.py"]
