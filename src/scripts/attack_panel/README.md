# 🎮 DDoS Attack Control Panel

Beautiful web-based interface for controlling the DDoS Attacks Framework.

## ✨ Features

- 🎨 **Modern UI** - Sleek dark theme with smooth animations
- 🚀 **12 Attack Types** - All attacks from ddos_attacks framework
- 📊 **Real-time Monitoring** - Live stats and logs
- 🎯 **Easy Configuration** - Simple form-based setup
- ⚡ **One-Click Launch** - Start attacks with a single click

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd /root/network_monitor/src/scripts/attack_panel
pip3 install -r requirements.txt
```

### 2. Start the Server

```bash
python3 server.py
```

### 3. Open in Browser

Navigate to: **http://localhost:5000**

## 📖 Usage

1. **Configure Attack**:
   - Enter target IP/hostname
   - Set port, duration, and threads
   
2. **Select Attack Type**:
   - Click on any attack card to select it
   - Green border indicates selection

3. **Launch**:
   - Click "🚀 Launch Attack"
   - Confirm the attack
   - Monitor real-time stats

4. **Stop** (if needed):
   - Click "🛑 Stop Attack" to terminate early

## 🎯 Available Attacks

### Layer 7 (No sudo required)
- **HTTP Flood** - High-volume HTTP requests
- **Slowloris** - Slow HTTP headers
- **Slow POST** - R.U.D.Y attack
- **Slow Read** - Slow response reading
- **Distributed HTTP** - Botnet HTTP flood

### Layer 3/4 (Requires sudo)
- **SYN Flood** - TCP SYN flood
- **UDP Flood** - UDP packet flood
- **ICMP Flood** - Ping of Death
- **Distributed SYN** - Botnet SYN flood
- **Distributed UDP** - Botnet UDP flood

### Amplification (No sudo required)
- **DNS Amplification** - DNS ANY queries
- **NTP Amplification** - NTP monlist

## 🔧 API Endpoints

### `POST /api/attack/start`
Start an attack
```json
{
  "attack_type": "http",
  "target": "192.168.1.100",
  "port": 80,
  "duration": 60,
  "threads": 100
}
```

### `POST /api/attack/stop`
Stop the running attack

### `GET /api/attack/status`
Get current attack status

### `GET /api/attacks/list`
List all available attack types

## ⚠️ Important Notes

1. **Sudo Attacks**: Layer 3/4 attacks require sudo privileges
   - Run server with sudo: `sudo python3 server.py`
   - Or configure sudoers for specific commands

2. **Legal Warning**: Use ONLY on systems you own or have permission to test

3. **Monitoring**: Check Grafana dashboard for detection results
   - URL: http://localhost:3000

## 📸 Screenshots

The UI features:
- Dark theme with gradient accents
- Interactive attack cards with hover effects
- Real-time statistics display
- Scrollable log console
- Responsive design

## 🛠️ Development

The panel consists of:
- `index.html` - Frontend UI (vanilla JS, no frameworks)
- `server.py` - Flask backend API
- `requirements.txt` - Python dependencies

## 🎨 Customization

Edit `index.html` to customize:
- Colors (CSS variables in `:root`)
- Attack cards layout
- Stats display
- Log formatting

---

**Created**: 2025-12-20
**Version**: 1.0.0
**Framework**: DDoS Attacks v2.0
