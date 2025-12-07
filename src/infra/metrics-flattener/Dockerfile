FROM python:3.11-slim
WORKDIR /app

COPY wait-for-it.sh /wait-for-it.sh
RUN chmod +x /wait-for-it.sh
COPY consumer.py .
RUN pip install confluent-kafka && \
    apt-get update && apt-get install -y netcat-traditional && \
    chmod +x /wait-for-it.sh
CMD ["/wait-for-it.sh", "kafka", "9092", "python", "consumer.py"]
