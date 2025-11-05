from kafka import KafkaConsumer, errors
import csv, json, os, time

KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "nginx-logs")
CSV_FILE = os.getenv("CSV_FILE", "/data/access_logs.csv")
FIELDS = os.getenv("CSV_FIELDS", "time,ip,method,uri,status,bytes,req_len,req_time,up_time,ua").split(",")

print(f"[+] Kafka brokers: {KAFKA_BROKERS}, topic: {KAFKA_TOPIC}, output file: {CSV_FILE}")

consumer = None
while consumer is None:
    try:
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BROKERS,
            value_deserializer=lambda m: json.loads(m.decode("utf-8"))
        )
    except errors.NoBrokersAvailable:
        print("[-] Kafka not ready, retrying in 5s...")
        time.sleep(5)

file_exists = os.path.isfile(CSV_FILE)
with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=FIELDS)
    if not file_exists:
        writer.writeheader()

    print(f"[+] Listening on topic {KAFKA_TOPIC}, writing to {CSV_FILE}")

    for msg in consumer:
        log = msg.value
        row = {k: log.get(k, "") for k in FIELDS}
        writer.writerow(row)
        f.flush()
