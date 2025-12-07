#!/usr/bin/env python3
"""
Real-time Network Capture with CICFlowMeter v2
- Direct real-time capture without PCAP files
- Optimized for continuous flow export to CSV
- Minimal latency between packet capture and flow output
"""

import logging
import sys
import os
import signal
from datetime import datetime
import subprocess
import time
from pathlib import Path

# Setup logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configuration
INTERFACE = os.getenv('INTERFACE', 'ens33')
OUTPUT_DIR = os.getenv('OUTPUT_DIR', '/output')
CAPTURE_DURATION = int(os.getenv('CAPTURE_INTERVAL', '30'))  # Use CAPTURE_INTERVAL env var

# Ensure output directory exists
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)


class RealtimeCICFlowMeter:
    """Real-time network capture with CICFlowMeter"""
    
    def __init__(self):
        self.interface = INTERFACE
        self.output_dir = OUTPUT_DIR
        self.duration = CAPTURE_DURATION
        self.running = True
        self.max_file_age = int(os.getenv('MAX_FILE_AGE_SECONDS', '300'))  # Keep files for 5 min default
        
        # Setup signal handler
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"\n🛑 Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def cleanup_old_files(self):
        """Remove old CSV files to prevent disk space issues"""
        try:
            current_time = time.time()
            removed_count = 0
            
            for filename in os.listdir(self.output_dir):
                if filename.startswith('flows_') and filename.endswith('.csv'):
                    filepath = os.path.join(self.output_dir, filename)
                    file_age = current_time - os.path.getmtime(filepath)
                    
                    if file_age > self.max_file_age:
                        try:
                            os.remove(filepath)
                            removed_count += 1
                            logger.debug(f"   Removed old file: {filename} (age: {int(file_age)}s)")
                        except Exception as e:
                            logger.warning(f"   Failed to remove {filename}: {e}")
            
            if removed_count > 0:
                logger.info(f"🗑️  Cleaned up {removed_count} old CSV files (>{self.max_file_age}s old)")
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        
    def validate_interface(self):
        """Validate that the network interface exists"""
        logger.info("=== Validating Network Interface ===")
        try:
            result = subprocess.run(
                ['ip', 'link', 'show', self.interface],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.info(f"✓ Interface {self.interface} available")
                # Get IP address
                result = subprocess.run(
                    ['ip', '-4', 'addr', 'show', self.interface],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if 'inet' in result.stdout:
                    ip = result.stdout.split('inet ')[1].split('/')[0]
                    logger.info(f"✓ IP Address: {ip}")
                    return True
            else:
                logger.error(f"✗ Interface {self.interface} not found")
                logger.info("Available interfaces:")
                result = subprocess.run(['ip', 'link', 'show'], capture_output=True, text=True)
                for line in result.stdout.split('\n'):
                    if ':' in line and 'inet' not in line:
                        logger.info(f"  {line.split(':')[1].strip()}")
                return False
        except Exception as e:
            logger.error(f"Error validating interface: {e}")
            return False
    
    def start_capture(self):
        """Start real-time packet capture with CICFlowMeter"""
        logger.info("=" * 60)
        logger.info("  Real-time Network Capture with CICFlowMeter v2")
        logger.info("=" * 60)
        
        if not self.validate_interface():
            logger.error("Failed to validate network interface")
            sys.exit(1)
        
        # Create health check file
        health_file = os.path.join(self.output_dir, 'health')
        Path(health_file).touch()
        
        logger.info(f"\n🚀 Starting periodic capture with rotation")
        logger.info(f"   Interface: {self.interface}")
        logger.info(f"   Output dir: {self.output_dir}")
        logger.info(f"   Rotation: {self.duration}s\n")
        
        try:
            while self.running:
                # Create new CSV file for this rotation
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                csv_file = os.path.join(self.output_dir, f'flows_{timestamp}.csv')
                
                logger.info(f"📝 Starting capture session: flows_{timestamp}.csv")
                
                # Start cicflowmeter
                cmd = [
                    'cicflowmeter',
                    '-i', self.interface,
                    '-c',  # CSV output
                    csv_file
                ]
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                
                # Run for specified duration
                start_time = time.time()
                
                try:
                    while time.time() - start_time < self.duration and self.running:
                        # Update health check
                        Path(health_file).touch()
                        
                        # Check if process is still running
                        if process.poll() is not None:
                            logger.error("CICFlowMeter process died unexpectedly!")
                            break
                        
                        # Log progress every 3 seconds
                        elapsed = time.time() - start_time
                        if int(elapsed) % 3 == 0:
                            logger.info(f"   📊 Capturing... {int(elapsed)}s / {self.duration}s")
                        
                        time.sleep(1)
                    
                    # Time's up - gracefully stop cicflowmeter
                    logger.info(f"⏰ Rotation time reached ({self.duration}s), stopping capture...")
                    
                    # Send SIGINT (Ctrl+C) to trigger CICFlowMeter's flush logic
                    process.send_signal(signal.SIGINT)
                    
                    # Wait for process to finish and flush data (CICFlowMeter needs time)
                    logger.info("   Waiting for CICFlowMeter to flush data to CSV...")
                    try:
                        process.wait(timeout=30)
                        logger.info("   ✓ CICFlowMeter stopped gracefully")
                    except subprocess.TimeoutExpired:
                        logger.warning("   ⚠️  Timeout after 30s, forcing kill...")
                        process.kill()
                        process.wait()
                    
                    # Check output file
                    if os.path.exists(csv_file):
                        file_size = os.path.getsize(csv_file)
                        try:
                            line_count = sum(1 for _ in open(csv_file)) - 1
                            logger.info(f"✅ Session completed: {line_count} flows, {file_size/1024:.1f} KB")
                        except:
                            logger.info(f"✅ Session completed: {file_size/1024:.1f} KB")
                    else:
                        logger.warning(f"⚠️  No output file created")
                    
                except Exception as e:
                    logger.error(f"Error during capture: {e}")
                    try:
                        process.terminate()
                        process.wait(timeout=5)
                    except:
                        process.kill()
                
                # Small delay before next rotation
                if self.running:
                    # Cleanup old files before next rotation
                    self.cleanup_old_files()
                    
                    logger.info(f"💤 Waiting 2s before next rotation...\n")
                    time.sleep(2)
                    
        except KeyboardInterrupt:
            logger.info("\n⚠️  Capture interrupted by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            sys.exit(1)
        finally:
            # Cleanup health file
            try:
                os.remove(health_file)
            except:
                pass


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    logger.info("\nReceived shutdown signal, cleaning up...")
    sys.exit(0)


def main():
    """Main entry point"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    capture = RealtimeCICFlowMeter()
    capture.start_capture()


if __name__ == '__main__':
    main()
