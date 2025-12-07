FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY telegram_notifier.py .

# Create non-root user
RUN useradd -m -u 1000 notifier && \
    chown -R notifier:notifier /app

USER notifier

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/metrics', timeout=5)" || exit 1

# Run the notifier
CMD ["python", "-u", "telegram_notifier.py"]
