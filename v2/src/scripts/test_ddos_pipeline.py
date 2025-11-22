#!/usr/bin/env python3
"""
Simple script to test DDoS detection pipeline
Generates synthetic network flows and sends to Kafka
"""

import json
import random
import time
from kafka import KafkaProducer
import argparse

def generate_normal_flow():
    """Generate a normal network flow"""
    return {
        "Flow ID": f"flow_{random.randint(100000, 999999)}",
        "Source IP": f"192.168.1.{random.randint(100, 200)}",
        "Source Port": random.randint(1024, 65535),
        "Destination IP": "10.0.0.1",
        "Destination Port": random.choice([80, 443, 8080]),
        "Protocol": 6,
        "Flow Duration": random.uniform(0.1, 5.0),
        "Total Fwd Packets": random.randint(5, 50),
        "Total Backward Packets": random.randint(5, 50),
        "Total Length of Fwd Packets": random.randint(500, 5000),
        "Total Length of Bwd Packets": random.randint(500, 5000),
        "Flow Bytes/s": random.uniform(1000, 10000),
        "Flow Packets/s": random.uniform(10, 100),
        "Flow IAT Mean": random.uniform(0.01, 0.1),
        "Flow IAT Std": random.uniform(0.001, 0.05),
        "Fwd IAT Mean": random.uniform(0.01, 0.1),
        "Bwd IAT Mean": random.uniform(0.01, 0.1),
        "Packet Length Mean": random.uniform(100, 1000),
        "Packet Length Std": random.uniform(10, 100),
        "Label": "BENIGN"
    }

def generate_ddos_flow():
    """Generate a DDoS attack flow"""
    return {
        "Flow ID": f"ddos_{random.randint(100000, 999999)}",
        "Source IP": f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}",
        "Source Port": random.randint(1024, 65535),
        "Destination IP": "10.0.0.1",  # Target server
        "Destination Port": 80,
        "Protocol": 6,
        "Flow Duration": random.uniform(0.001, 0.1),  # Very short
        "Total Fwd Packets": random.randint(100, 1000),  # High packet count
        "Total Backward Packets": random.randint(0, 10),  # Low response
        "Total Length of Fwd Packets": random.randint(5000, 50000),  # High volume
        "Total Length of Bwd Packets": random.randint(0, 500),
        "Flow Bytes/s": random.uniform(50000, 500000),  # Very high rate
        "Flow Packets/s": random.uniform(500, 5000),    # Very high packet rate
        "Flow IAT Mean": random.uniform(0.0001, 0.001), # Very small intervals
        "Flow IAT Std": random.uniform(0.00001, 0.0001),
        "Fwd IAT Mean": random.uniform(0.0001, 0.001),
        "Bwd IAT Mean": random.uniform(0.01, 0.1),
        "Packet Length Mean": random.uniform(50, 200),   # Small packets
        "Packet Length Std": random.uniform(5, 20),
        "Label": "DDoS"
    }

def main():
    parser = argparse.ArgumentParser(description='Test DDoS Detection Pipeline')
    parser.add_argument('--kafka-server', default='localhost:9092', help='Kafka bootstrap server')
    parser.add_argument('--topic', default='network-flows', help='Kafka topic to send flows')
    parser.add_argument('--normal-flows', type=int, default=100, help='Number of normal flows to generate')
    parser.add_argument('--ddos-flows', type=int, default=20, help='Number of DDoS flows to generate')
    parser.add_argument('--interval', type=float, default=0.1, help='Interval between flows (seconds)')
    parser.add_argument('--burst', action='store_true', help='Send DDoS flows in burst mode')
    
    args = parser.parse_args()
    
    print(f"🧪 Testing DDoS Detection Pipeline")
    print(f"📡 Kafka Server: {args.kafka_server}")
    print(f"📝 Topic: {args.topic}")
    print(f"✅ Normal flows: {args.normal_flows}")
    print(f"🔴 DDoS flows: {args.ddos_flows}")
    print(f"⏱️  Interval: {args.interval}s")
    print()
    
    try:
        # Create Kafka producer
        producer = KafkaProducer(
            bootstrap_servers=[args.kafka_server],
            value_serializer=lambda x: json.dumps(x).encode('utf-8')
        )
        
        print("🚀 Starting flow generation...")
        
        # Send normal flows
        print(f"📤 Sending {args.normal_flows} normal flows...")
        for i in range(args.normal_flows):
            flow = generate_normal_flow()
            producer.send(args.topic, flow)
            
            if (i + 1) % 10 == 0:
                print(f"  ✅ Sent {i + 1} normal flows")
            
            time.sleep(args.interval)
        
        # Send DDoS flows
        print(f"📤 Sending {args.ddos_flows} DDoS attack flows...")
        
        if args.burst:
            print("💥 Burst mode: Sending DDoS flows rapidly...")
            burst_interval = 0.01  # Very fast for burst
        else:
            burst_interval = args.interval
        
        for i in range(args.ddos_flows):
            flow = generate_ddos_flow()
            producer.send(args.topic, flow)
            
            if (i + 1) % 5 == 0:
                print(f"  🔴 Sent {i + 1} DDoS flows")
            
            time.sleep(burst_interval)
        
        # Flush and close
        producer.flush()
        producer.close()
        
        print()
        print("✅ Flow generation completed!")
        print("🔍 Check DDoS Detector logs:")
        print("   docker logs ddos-detector")
        print("📊 Monitor alerts topic:")
        print("   docker exec -it ids_kafka kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic security-alerts")
        print("📈 View Prometheus metrics:")
        print("   http://localhost:9090")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("💡 Make sure Kafka is running: ./ddos-pipeline.sh status")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())