"""
Telegram Notifier với Anti-Spam Mechanism

Features:
1. Rate Limiting - Giới hạn số alerts trong time window
2. Deduplication - Không gửi alert trùng lặp
3. Alert Aggregation - Gộp nhiều alerts thành summary
4. Cooldown Period - Tạm ngừng sau khi quá rate limit
5. Critical Bypass - Luôn gửi CRITICAL alerts
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from collections import defaultdict, deque
import requests
from kafka import KafkaConsumer
from kafka.errors import KafkaError
import prometheus_client as prom
from prometheus_client import Counter, Gauge, start_http_server

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus metrics
ALERTS_RECEIVED = Counter('telegram_alerts_received_total', 'Total alerts received', ['severity'])
ALERTS_SENT = Counter('telegram_alerts_sent_total', 'Total alerts sent successfully', ['severity'])
ALERTS_FAILED = Counter('telegram_alerts_failed_total', 'Total alerts failed to send', ['reason'])
ALERTS_SUPPRESSED = Counter('telegram_alerts_suppressed_total', 'Total alerts suppressed', ['reason'])
ALERTS_AGGREGATED = Counter('telegram_alerts_aggregated_total', 'Total alerts aggregated')
NOTIFICATION_TIME = prom.Histogram('telegram_notification_seconds', 'Time to send notification')
ACTIVE_ATTACKS = Gauge('telegram_active_attacks', 'Number of active attacks tracked')


class TelegramNotifier:
    """Telegram notification service với anti-spam"""
    
    def __init__(self):
        # Telegram config
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not self.bot_token or not self.chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set")
        
        self.telegram_api_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        # Anti-spam config
        self.rate_limit_window = int(os.getenv('RATE_LIMIT_WINDOW', '300'))
        self.max_alerts_per_window = int(os.getenv('MAX_ALERTS_PER_WINDOW', '5'))
        self.min_interval_seconds = int(os.getenv('MIN_ALERT_INTERVAL', '60'))
        self.aggregation_window = int(os.getenv('AGGREGATION_WINDOW', '180'))
        self.cooldown_after_burst = int(os.getenv('COOLDOWN_AFTER_BURST', '600'))
        
        # Alert tracking
        self.alert_history = deque(maxlen=100)
        self.last_sent_time = None
        self.seen_alert_ids = set()
        self.pending_alerts = []
        self.attack_summary = defaultdict(dict)
        self.last_summary_time = None
        self.in_cooldown = False
        self.cooldown_until = None
        
        # Initialize Kafka
        kafka_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
        self.alert_topic = os.getenv('KAFKA_ALERT_TOPIC', 'ddos-alerts')
        
        logger.info(f"Initializing Telegram Notifier")
        logger.info(f"Kafka: {kafka_servers}, Topic: {self.alert_topic}")
        logger.info(f"Chat ID: {self.chat_id}")
        
        try:
            self.consumer = KafkaConsumer(
                self.alert_topic,
                bootstrap_servers=kafka_servers.split(','),
                group_id='telegram-notifier-group',
                value_deserializer=lambda m: m.decode('utf-8'),
                auto_offset_reset='latest',
                enable_auto_commit=True,
                max_poll_records=10,
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000
            )
            logger.info("Kafka consumer initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka: {e}")
            raise
        
        # Test Telegram
        self._test_telegram()
        
        logger.info(f"Anti-spam: max {self.max_alerts_per_window} alerts per {self.rate_limit_window}s, "
                   f"min interval {self.min_interval_seconds}s")
    
    def _test_telegram(self):
        """Test Telegram connection"""
        try:
            response = requests.get(f"{self.telegram_api_url}/getMe", timeout=5)
            if response.status_code == 200:
                bot_info = response.json()
                logger.info(f"Telegram bot: {bot_info['result']['username']}")
                self.send_message("🤖 Telegram Notifier started with anti-spam protection!")
            else:
                logger.error(f"Failed to connect: {response.text}")
        except Exception as e:
            logger.error(f"Telegram test failed: {e}")
    
    def send_message(self, message, parse_mode='HTML'):
        """Send message to Telegram"""
        try:
            with NOTIFICATION_TIME.time():
                response = requests.post(
                    f"{self.telegram_api_url}/sendMessage",
                    json={
                        'chat_id': self.chat_id,
                        'text': message,
                        'parse_mode': parse_mode,
                        'disable_web_page_preview': True
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    return True
                else:
                    logger.error(f"Send failed: {response.text}")
                    ALERTS_FAILED.labels(reason='api_error').inc()
                    return False
        except Exception as e:
            logger.error(f"Send error: {e}")
            ALERTS_FAILED.labels(reason='exception').inc()
            return False
    
    def should_send_alert(self, alert):
        """Quyết định có nên gửi alert không"""
        alert_id = alert.get('alert_id', 'unknown')
        now = datetime.now()
        
        # 1. Deduplication
        if alert_id in self.seen_alert_ids:
            return False, 'duplicate'
        
        # 2. Check cooldown
        if self.in_cooldown and self.cooldown_until:
            if now < self.cooldown_until:
                return False, 'cooldown'
            else:
                self.in_cooldown = False
                self.cooldown_until = None
                logger.info("Cooldown ended")
        
        # 3. Rate limit check
        cutoff = now - timedelta(seconds=self.rate_limit_window)
        recent = [t for t in self.alert_history if t > cutoff]
        
        if len(recent) >= self.max_alerts_per_window:
            if not self.in_cooldown:
                self.in_cooldown = True
                self.cooldown_until = now + timedelta(seconds=self.cooldown_after_burst)
                logger.warning(f"Rate limit! Cooldown until {self.cooldown_until}")
                self.send_message(
                    f"⚠️ <b>Alert Rate Limit</b>\n\n"
                    f"{len(recent)} alerts trong {self.rate_limit_window}s.\n"
                    f"Cooldown: {self.cooldown_after_burst}s\n"
                    f"Chuyển sang chế độ aggregation."
                )
            return False, 'rate_limit'
        
        # 4. Min interval
        if self.last_sent_time:
            elapsed = (now - self.last_sent_time).total_seconds()
            if elapsed < self.min_interval_seconds:
                return False, 'min_interval'
        
        # 5. Always allow CRITICAL
        if alert.get('severity', '').upper() == 'CRITICAL':
            return True, 'critical'
        
        return True, 'ok'
    
    def format_alert(self, alert):
        """Format alert thành Telegram message"""
        severity = alert.get('severity', 'UNKNOWN').upper()
        emoji = {'LOW': '⚠️', 'MEDIUM': '🟡', 'HIGH': '🔴', 'CRITICAL': '🚨'}.get(severity, '📌')
        
        timestamp = alert.get('timestamp', datetime.now().isoformat())
        if isinstance(timestamp, str):
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamp = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                pass
        
        # Detect alert source (rule-based vs ML)
        source = alert.get('source', 'unknown')
        
        msg = f"{emoji} <b>DDoS ALERT - {severity}</b>\n\n"
        msg += f"<b>Time:</b> {timestamp}\n"
        
        # Attack type - handle both formats
        rule_name = None
        if 'rule_name' in alert:
            # Rule-based detector format
            rule_name = alert.get('rule_name', 'Unknown')
            msg += f"<b>Type:</b> {rule_name}\n"
            msg += f"<b>Rule:</b> {alert.get('rule_id', 'N/A')}\n"
            msg += f"<b>Description:</b> {alert.get('description', 'N/A')}\n"
        else:
            # ML detector format (legacy)
            msg += f"<b>Type:</b> {alert.get('attack_type', 'Unknown')}\n"
            msg += f"<b>Target:</b> <code>{alert.get('target_ip', 'N/A')}</code>\n"
            msg += f"<b>Flows:</b> {alert.get('flow_count', 0)}\n"
        
        # Confidence - handle both formats
        confidence = alert.get('confidence', alert.get('avg_confidence', 0))
        if isinstance(confidence, (int, float)):
            msg += f"<b>Confidence:</b> {confidence:.1%}\n"
        
        # Window Stats - thêm thông tin quan trọng theo loại tấn công
        window_stats = alert.get('window_stats', {})
        if window_stats:
            msg += f"\n<b>📊 Attack Statistics:</b>\n"
            
            # Luôn hiển thị total flows
            total_flows = window_stats.get('total_flows', 0)
            msg += f"  • Total Flows: <b>{total_flows:,}</b>\n"
            
            # Hiển thị metrics đặc trưng theo loại tấn công
            if rule_name:
                if 'SYN Flood' in rule_name or 'SYN' in rule_name.upper():
                    # SYN Flood Attack - focus on SYN/ACK metrics
                    syn_count = window_stats.get('syn_flag_count', 0)
                    ack_count = window_stats.get('ack_flag_count', 0)
                    syn_ack_ratio = window_stats.get('syn_ack_ratio', 0)
                    tcp_packets = window_stats.get('tcp_packet_count', 0)
                    
                    msg += f"  • SYN Packets: <b>{int(syn_count):,}</b>\n"
                    msg += f"  • ACK Packets: <b>{int(ack_count):,}</b>\n"
                    msg += f"  • SYN/ACK Ratio: <b>{syn_ack_ratio:.2%}</b>\n"
                    msg += f"  • TCP Packets: <b>{int(tcp_packets):,}</b>\n"
                
                elif 'UDP Flood' in rule_name or 'UDP' in rule_name.upper():
                    # UDP Flood Attack - focus on UDP metrics
                    udp_packets = window_stats.get('udp_packet_count', 0)
                    unique_dst_ports = window_stats.get('unique_dst_ports', 0)
                    packets_per_ip = window_stats.get('packets_per_ip', 0)
                    
                    msg += f"  • UDP Packets: <b>{int(udp_packets):,}</b>\n"
                    msg += f"  • Unique Dst Ports: <b>{unique_dst_ports}</b>\n"
                    msg += f"  • Packets/IP: <b>{packets_per_ip:.1f}</b>\n"
                
                elif 'ICMP Flood' in rule_name or 'ICMP' in rule_name.upper():
                    # ICMP Flood Attack - focus on ICMP metrics
                    icmp_packets = window_stats.get('icmp_packet_count', 0)
                    packets_per_ip = window_stats.get('packets_per_ip', 0)
                    
                    msg += f"  • ICMP Packets: <b>{int(icmp_packets):,}</b>\n"
                    msg += f"  • Packets/IP: <b>{packets_per_ip:.1f}</b>\n"
                
                elif 'Port Scan' in rule_name or 'SCAN' in rule_name.upper():
                    # Port Scan - focus on port diversity
                    unique_dst_ports = window_stats.get('unique_dst_ports', 0)
                    unique_dst_ports_per_ip = window_stats.get('unique_dst_ports_per_ip', 0)
                    unique_src_ips = window_stats.get('unique_src_ips', 0)
                    
                    msg += f"  • Unique Dst Ports: <b>{unique_dst_ports}</b>\n"
                    msg += f"  • Ports/IP: <b>{unique_dst_ports_per_ip:.1f}</b>\n"
                    msg += f"  • Unique Src IPs: <b>{unique_src_ips}</b>\n"
                
                elif 'Slowloris' in rule_name or 'SLOW' in rule_name.upper():
                    # Slowloris - focus on connection metrics
                    tcp_packets = window_stats.get('tcp_packet_count', 0)
                    packets_per_ip = window_stats.get('packets_per_ip', 0)
                    flows_per_ip = window_stats.get('flows_per_ip', 0)
                    
                    msg += f"  • TCP Packets: <b>{int(tcp_packets):,}</b>\n"
                    msg += f"  • Flows/IP: <b>{flows_per_ip:.1f}</b>\n"
                    msg += f"  • Packets/IP: <b>{packets_per_ip:.1f}</b>\n"
                
                else:
                    # Generic attack - show general metrics
                    unique_src_ips = window_stats.get('unique_src_ips', 0)
                    unique_dst_ports = window_stats.get('unique_dst_ports', 0)
                    
                    msg += f"  • Unique Src IPs: <b>{unique_src_ips}</b>\n"
                    if unique_dst_ports:
                        msg += f"  • Unique Dst Ports: <b>{unique_dst_ports}</b>\n"
            else:
                # ML detector - show general stats
                unique_src_ips = window_stats.get('unique_src_ips', 0)
                if unique_src_ips:
                    msg += f"  • Unique Src IPs: <b>{unique_src_ips}</b>\n"
        
        # Attacker IPs
        ips = alert.get('attacker_ips', [])
        if ips:
            msg += f"\n<b>🎯 Attackers ({len(ips)}):</b>\n"
            for ip in ips[:5]:
                msg += f"  • <code>{ip}</code>\n"
            if len(ips) > 5:
                msg += f"  ... +{len(ips)-5} more\n"
        
        # Action (for rule-based)
        action = alert.get('action')
        if action:
            msg += f"\n<b>⚡ Action:</b> {action}\n"
        
        # Matched conditions (for rule-based)
        matched_conditions = alert.get('matched_conditions', [])
        if matched_conditions:
            msg += f"\n<b>✓ Matched Conditions:</b>\n"
            for cond in matched_conditions[:3]:
                msg += f"  • {cond}\n"
            if len(matched_conditions) > 3:
                msg += f"  ... +{len(matched_conditions)-3} more\n"
        
        msg += f"\n<i>ID: {alert.get('alert_id', 'N/A')}</i>"
        return msg

    
    def add_to_aggregation(self, alert):
        """Thêm alert vào buffer aggregation"""
        self.pending_alerts.append(alert)
        
        # Track attackers
        for ip in alert.get('attacker_ips', []):
            if ip not in self.attack_summary:
                self.attack_summary[ip] = {
                    'count': 0,
                    'first_seen': datetime.now(),
                    'severities': []
                }
            self.attack_summary[ip]['count'] += 1
            self.attack_summary[ip]['last_seen'] = datetime.now()
            self.attack_summary[ip]['severities'].append(alert.get('severity', 'unknown'))
        
        ALERTS_AGGREGATED.inc()
        ACTIVE_ATTACKS.set(len(self.attack_summary))
    
    def should_send_summary(self):
        """Kiểm tra có nên gửi summary không"""
        if not self.pending_alerts:
            return False
        
        # Send if >= 10 alerts or aggregation window passed
        if len(self.pending_alerts) >= 10:
            return True
        
        now = datetime.now()
        if self.last_summary_time:
            elapsed = (now - self.last_summary_time).total_seconds()
            return elapsed >= self.aggregation_window
        
        return False
    
    def send_summary(self):
        """Gửi aggregated summary"""
        if not self.pending_alerts:
            return
        
        num = len(self.pending_alerts)
        msg = f"📊 <b>ALERT SUMMARY</b>\n\n"
        msg += f"<b>Total:</b> {num} alerts\n"
        msg += f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # Severity breakdown
        severities = defaultdict(int)
        for a in self.pending_alerts:
            severities[a.get('severity', 'unknown')] += 1
        
        msg += "<b>By Severity:</b>\n"
        for sev, count in sorted(severities.items(), reverse=True):
            emoji = {'CRITICAL': '🚨', 'HIGH': '🔴', 'MEDIUM': '🟡', 'LOW': '⚠️'}.get(sev, '📌')
            msg += f"  {emoji} {sev}: {count}\n"
        
        # Top attackers
        if self.attack_summary:
            msg += f"\n<b>Top Attackers ({len(self.attack_summary)}):</b>\n"
            sorted_attackers = sorted(
                self.attack_summary.items(),
                key=lambda x: x[1]['count'],
                reverse=True
            )[:10]
            
            for ip, data in sorted_attackers:
                msg += f"  • <code>{ip}</code>: {data['count']} attacks\n"
            
            if len(self.attack_summary) > 10:
                msg += f"  ... +{len(self.attack_summary)-10} more\n"
        
        msg += f"\n<i>Aggregated from {num} alerts</i>"
        
        success = self.send_message(msg)
        if success:
            logger.info(f"Sent summary for {num} alerts")
            self.last_summary_time = datetime.now()
            self.pending_alerts.clear()
            self.attack_summary.clear()
            ACTIVE_ATTACKS.set(0)
    
    def process_alert(self, alert):
        """Xử lý alert với anti-spam logic"""
        severity = alert.get('severity', 'unknown')
        alert_id = alert.get('alert_id', 'unknown')
        
        ALERTS_RECEIVED.labels(severity=severity).inc()
        logger.info(f"Processing: {alert_id}")
        
        try:
            should_send, reason = self.should_send_alert(alert)
            
            if should_send:
                # Send immediately
                msg = self.format_alert(alert)
                success = self.send_message(msg)
                
                if success:
                    ALERTS_SENT.labels(severity=severity).inc()
                    logger.info(f"Sent: {alert_id}")
                    self.alert_history.append(datetime.now())
                    self.last_sent_time = datetime.now()
                    self.seen_alert_ids.add(alert_id)
            else:
                # Suppress and aggregate
                ALERTS_SUPPRESSED.labels(reason=reason).inc()
                logger.info(f"Suppressed: {alert_id} ({reason})")
                self.add_to_aggregation(alert)
                
                if self.should_send_summary():
                    self.send_summary()
        
        except Exception as e:
            logger.error(f"Process error: {e}")
            ALERTS_FAILED.labels(reason='processing_error').inc()
    
    def run(self):
        """Main loop"""
        logger.info("Starting main loop")
        last_check = datetime.now()
        
        try:
            for message in self.consumer:
                try:
                    # Parse JSON
                    try:
                        alert = json.loads(message.value)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON: {e}")
                        ALERTS_FAILED.labels(reason='decode_error').inc()
                        continue
                    
                    self.process_alert(alert)
                    
                    # Periodic summary check
                    now = datetime.now()
                    if (now - last_check).total_seconds() >= 30:
                        if self.should_send_summary():
                            self.send_summary()
                        last_check = now
                
                except Exception as e:
                    logger.error(f"Message error: {e}")
                    ALERTS_FAILED.labels(reason='processing_error').inc()
        
        except KeyboardInterrupt:
            logger.info("Shutdown signal")
            if self.pending_alerts:
                logger.info("Sending final summary")
                self.send_summary()
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            raise
        finally:
            logger.info("Closing consumer")
            self.consumer.close()


def main():
    """Entry point"""
    logger.info("=" * 60)
    logger.info("Telegram Notifier for DDoS Detection (with Anti-Spam)")
    logger.info("=" * 60)
    
    # Start metrics server
    port = int(os.getenv('METRICS_PORT', '8000'))
    start_http_server(port)
    logger.info(f"Metrics at ::{port}/metrics")
    
    # Run notifier
    try:
        notifier = TelegramNotifier()
        notifier.run()
    except Exception as e:
        logger.error(f"Failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
