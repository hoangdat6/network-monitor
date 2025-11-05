FROM python:3.11-slim

WORKDIR /app
COPY kafka-to-csv.py .
COPY wait-for-it.sh /wait-for-it.sh

RUN pip install kafka-python && \
    apt-get update && apt-get install -y netcat-traditional && \
    chmod +x /wait-for-it.sh

CMD ["/wait-for-it.sh", "kafka", "9092", "python", "kafka-to-csv.py"]
