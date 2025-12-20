FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    hping3 \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Copy attack framework
COPY ../ddos_attacks /app/ddos_attacks

# Copy web panel
COPY . /app/attack_panel

# Install Python dependencies
RUN pip install --no-cache-dir Flask flask-cors

# Expose port
EXPOSE 5000

# Set working directory
WORKDIR /app/attack_panel

# Run server
CMD ["python", "server.py"]
