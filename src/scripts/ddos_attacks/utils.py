"""
Utility functions for DDoS attack framework
"""

import subprocess
import socket
from datetime import datetime
from typing import Optional


class Colors:
    """Terminal colors for output"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'  # No Color


def log(level: str, message: str, verbose: bool = True):
    """Log message with color and timestamp"""
    if not verbose:
        return
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    color_map = {
        'INFO': Colors.BLUE,
        'SUCCESS': Colors.GREEN,
        'WARNING': Colors.YELLOW,
        'ERROR': Colors.RED,
        'ATTACK': Colors.MAGENTA,
        'DEBUG': Colors.CYAN,
    }
    
    color = color_map.get(level, Colors.NC)
    print(f"{color}[{level}]{Colors.NC} {timestamp} - {message}")


def check_tool_installed(tool: str) -> bool:
    """Check if a command-line tool is installed"""
    try:
        subprocess.run(['which', tool], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


def validate_target(target: str) -> bool:
    """Validate target IP/hostname"""
    try:
        socket.gethostbyname(target)
        return True
    except socket.gaierror:
        return False


def resolve_target(target: str) -> Optional[str]:
    """Resolve hostname to IP address"""
    try:
        return socket.gethostbyname(target)
    except socket.gaierror:
        return None


def format_rate(packets: int, duration: float) -> str:
    """Format packet rate for display"""
    if duration <= 0:
        return "N/A"
    rate = packets / duration
    if rate >= 1000000:
        return f"{rate/1000000:.2f}M pps"
    elif rate >= 1000:
        return f"{rate/1000:.2f}K pps"
    else:
        return f"{rate:.2f} pps"


def format_bytes(bytes_count: int) -> str:
    """Format bytes for display"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_count < 1024:
            return f"{bytes_count:.2f} {unit}"
        bytes_count /= 1024
    return f"{bytes_count:.2f} TB"
