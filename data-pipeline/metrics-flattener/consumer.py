from confluent_kafka import Consumer, Producer
import json
from collections import defaultdict

KAFKA_BROKER = "kafka:9092"
TOPIC_IN = "raw_metrics"
TOPIC_OUT = "node_metrics_flat"

c = Consumer({
    'bootstrap.servers': KAFKA_BROKER,
    'group.id': 'metric-flattener',
    'auto.offset.reset': 'earliest'
})

p = Producer({'bootstrap.servers': KAFKA_BROKER})

c.subscribe([TOPIC_IN])

# cache tạm để gom 5 metric cùng (instance, timestamp)
cache = defaultdict(dict)

TARGET_METRICS = {
    "node:cpu_usage:ratio": "cpu_usage",
    "node:memory_usage:bytes": "memory_usage",
    "node:disk_usage:bytes": "disk_usage",
    "node:network_rx:rate": "network_rx",
    "node:network_tx:rate": "network_tx"
}

print("Listening...")

while True:
    msg = c.poll(1.0)
    if msg is None:
        continue
    if msg.error():
        print("Error:", msg.error())
        continue

    try:
        data = json.loads(msg.value().decode("utf-8"))

        # ví dụ data Adapter push sẽ có dạng: {"labels":{"__name__":"node:cpu_usage:ratio", "instance":"node1"},"value":123.4,"timestamp":...}
        metric_name = data["labels"]["__name__"]
        if metric_name not in TARGET_METRICS:
            continue

        instance = data["labels"].get("instance", "unknown")
        ts = data["timestamp"]
        val = data["value"]

        key = (instance, ts)
        cache[key]["timestamp"] = ts
        cache[key]["instance"] = instance
        cache[key][TARGET_METRICS[metric_name]] = val

        # check nếu đã đủ 5 metric thì xuất JSON
        if all(k in cache[key] for k in [
            "cpu_usage", "memory_usage", "disk_usage", "network_rx", "network_tx"
        ]):
            flat = cache[key]
            p.produce(TOPIC_OUT, json.dumps(flat).encode("utf-8"))
            p.flush()
            print("Published:", flat)
            del cache[key]

    except Exception as e:
        print("Parse error:", e)

c.close()
