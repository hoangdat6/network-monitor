FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY detector.py .
COPY rule_engine.py .
COPY window_manager.py .
COPY rules.yaml .

# Expose Prometheus metrics port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Run detector
CMD ["python", "-u", "detector.py"]
