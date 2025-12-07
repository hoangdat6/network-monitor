FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy detector code and rules
COPY ddos_detector.py .
COPY detection_rules.yaml .

# Copy models (will be mounted from volume)
RUN mkdir -p /models

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000')" || exit 1

CMD ["python", "-u", "ddos_detector.py"]
