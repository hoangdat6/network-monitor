import socket
try:
    sock = socket.create_connection(("kafka", 9092), timeout=5)
    print("[+] Connected to Kafka:9092 OK")
    sock.close()
except Exception as e:
    print("[-] Cannot connect to Kafka:", e)
