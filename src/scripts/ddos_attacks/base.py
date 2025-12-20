"""
Base class for all DDoS attacks
"""

import time
from abc import ABC, abstractmethod
from typing import Dict, Any
from .utils import log, validate_target


class AttackBase(ABC):
    """Base class for all attack types"""
    
    def __init__(self, target: str, port: int = 80, verbose: bool = True):
        """
        Initialize attack
        
        Args:
            target: Target IP or hostname
            port: Target port
            verbose: Enable verbose logging
        """
        self.target = target
        self.port = port
        self.verbose = verbose
        self.stop_flag = False
        
        # Attack statistics
        self.stats = {
            'packets_sent': 0,
            'bytes_sent': 0,
            'requests_sent': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None,
        }
        
        # Validate target
        if not validate_target(target):
            raise ValueError(f"Invalid target: {target}")
    
    @abstractmethod
    def execute(self, duration: int, **kwargs) -> bool:
        """
        Execute the attack
        
        Args:
            duration: Attack duration in seconds
            **kwargs: Additional attack-specific parameters
            
        Returns:
            True if attack completed successfully
        """
        pass
    
    def start(self):
        """Mark attack start time"""
        self.stats['start_time'] = time.time()
        self.stop_flag = False
    
    def stop(self):
        """Mark attack end time and set stop flag"""
        self.stats['end_time'] = time.time()
        self.stop_flag = True
    
    def get_duration(self) -> float:
        """Get actual attack duration"""
        if self.stats['start_time'] and self.stats['end_time']:
            return self.stats['end_time'] - self.stats['start_time']
        return 0.0
    
    def get_rate(self) -> float:
        """Get packets per second rate"""
        duration = self.get_duration()
        if duration > 0:
            return self.stats['packets_sent'] / duration
        return 0.0
    
    def print_stats(self):
        """Print attack statistics"""
        duration = self.get_duration()
        rate = self.get_rate()
        
        log('INFO', f"{'='*60}", self.verbose)
        log('INFO', f"Attack Statistics for {self.__class__.__name__}", self.verbose)
        log('INFO', f"{'='*60}", self.verbose)
        log('INFO', f"Target: {self.target}:{self.port}", self.verbose)
        log('INFO', f"Duration: {duration:.2f} seconds", self.verbose)
        log('INFO', f"Packets sent: {self.stats['packets_sent']:,}", self.verbose)
        log('INFO', f"Bytes sent: {self.stats['bytes_sent']:,}", self.verbose)
        log('INFO', f"Requests sent: {self.stats['requests_sent']:,}", self.verbose)
        log('INFO', f"Errors: {self.stats['errors']:,}", self.verbose)
        log('INFO', f"Rate: {rate:.2f} packets/sec", self.verbose)
        log('INFO', f"{'='*60}", self.verbose)
    
    def log(self, level: str, message: str):
        """Convenience method for logging"""
        log(level, message, self.verbose)
