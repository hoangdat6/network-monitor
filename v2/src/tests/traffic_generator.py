#!/usr/bin/env python3
"""
Simple Traffic Generator

Generates normal and suspicious traffic for testing.
Uses only Python standard library - no external dependencies.
"""

import socket
import time
import random
import threading
from datetime import datetime

class TrafficGenerator:
    """Generate network traffic for testing"""
    
    def __init__(self, target: str, port: int = 80):
        self.target = target
        self.port = port
        self.stop_flag = False
    
    def send_http_request(self, method: str = 'GET', path: str = '/'):
        """Send single HTTP request"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self.target, self.port))
            
            request = f"{method} {path} HTTP/1.1\r\n"
            request += f"Host: {self.target}\r\n"
            request += "User-Agent: TestClient/1.0\r\n"
            request += "Connection: close\r\n\r\n"
            
            sock.sendall(request.encode())
            response = sock.recv(1024)
            sock.close()
            
            return True
        except Exception as e:
            return False
    
    def normal_traffic(self, duration: int = 60, rate: int = 5):
        """Generate normal traffic pattern"""
        print(f"🟢 Generating normal traffic ({rate} req/s for {duration}s)")
        
        end_time = time.time() + duration
        count = 0
        
        while time.time() < end_time and not self.stop_flag:
            # Normal browsing patterns
            paths = ['/', '/about', '/contact', '/products', '/api/data']
            path = random.choice(paths)
            
            if self.send_http_request('GET', path):
                count += 1
            
            # Human-like delays
            time.sleep(1.0 / rate)
            
            if count % 50 == 0:
                print(f"  Normal traffic: {count} requests sent")
        
        print(f"✅ Normal traffic completed: {count} requests")
    
    def suspicious_traffic(self, duration: int = 30, rate: int = 50):
        """Generate suspicious traffic pattern"""
        print(f"🔴 Generating suspicious traffic ({rate} req/s for {duration}s)")
        
        end_time = time.time() + duration
        count = 0
        
        while time.time() < end_time and not self.stop_flag:
            # Suspicious patterns
            paths = [
                '/',
                '/admin',
                '/../etc/passwd',
                '/wp-admin',
                '/phpmyadmin',
                '/' + 'A' * 1000,  # Long path
            ]
            path = random.choice(paths)
            
            if self.send_http_request('GET', path):
                count += 1
            
            # Very fast requests
            time.sleep(1.0 / rate)
            
            if count % 100 == 0:
                print(f"  Suspicious traffic: {count} requests sent")
        
        print(f"✅ Suspicious traffic completed: {count} requests")
    
    def burst_traffic(self, bursts: int = 3, burst_size: int = 100):
        """Generate burst traffic"""
        print(f"💥 Generating burst traffic ({bursts} bursts of {burst_size} requests)")
        
        for i in range(bursts):
            print(f"  Burst {i+1}/{bursts}...")
            
            threads = []
            for _ in range(burst_size):
                t = threading.Thread(target=self.send_http_request)
                t.start()
                threads.append(t)
            
            for t in threads:
                t.join(timeout=10)
            
            if i < bursts - 1:
                wait = random.randint(5, 15)
                print(f"  Waiting {wait}s before next burst...")
                time.sleep(wait)
        
        print(f"✅ Burst traffic completed")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Simple Traffic Generator')
    parser.add_argument('target', help='Target IP or hostname')
    parser.add_argument('-p', '--port', type=int, default=80, help='Target port')
    parser.add_argument('-t', '--type', 
                       choices=['normal', 'suspicious', 'burst', 'mixed'],
                       default='normal',
                       help='Traffic type')
    parser.add_argument('-d', '--duration', type=int, default=60,
                       help='Duration in seconds')
    parser.add_argument('-r', '--rate', type=int, default=10,
                       help='Requests per second')
    
    args = parser.parse_args()
    
    gen = TrafficGenerator(args.target, args.port)
    
    print("\n" + "="*60)
    print(f"🚦 Traffic Generator")
    print("="*60)
    print(f"Target: {args.target}:{args.port}")
    print(f"Type: {args.type}")
    print(f"Duration: {args.duration}s")
    print("="*60 + "\n")
    
    try:
        if args.type == 'normal':
            gen.normal_traffic(args.duration, args.rate)
        elif args.type == 'suspicious':
            gen.suspicious_traffic(args.duration, args.rate)
        elif args.type == 'burst':
            gen.burst_traffic(bursts=3, burst_size=100)
        elif args.type == 'mixed':
            print("Mixed traffic pattern:")
            gen.normal_traffic(20, 5)
            time.sleep(5)
            gen.suspicious_traffic(30, 30)
            time.sleep(5)
            gen.burst_traffic(2, 50)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        gen.stop_flag = True
    
    print("\n" + "="*60)
    print("💡 Check Detection:")
    print("="*60)
    print("docker logs ids_ddos_detector | tail -50")
    print("curl http://localhost:8001/metrics | grep ddos")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
