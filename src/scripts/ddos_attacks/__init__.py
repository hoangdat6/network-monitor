"""
DDoS Attack Testing Framework
A modular framework for testing DDoS detection systems
"""

__version__ = "2.0.0"
__author__ = "Network Security Team"

from .base import AttackBase
from .layer3_attacks import SYNFlood, UDPFlood, ICMPFlood
from .layer7_attacks import HTTPFlood, Slowloris
from .amplification import DNSAmplification, NTPAmplification, MemcachedAmplification
from .slow_attacks import SlowPOST, SlowRead
from .distributed import DistributedAttack

__all__ = [
    'AttackBase',
    'SYNFlood',
    'UDPFlood', 
    'ICMPFlood',
    'HTTPFlood',
    'Slowloris',
    'DNSAmplification',
    'NTPAmplification',
    'MemcachedAmplification',
    'SlowPOST',
    'SlowRead',
    'DistributedAttack',
]
