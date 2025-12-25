"""
Window Manager for Aggregation Rules

Maintains sliding time windows and calculates statistics for rule evaluation.
"""

import logging
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List
import time

logger = logging.getLogger(__name__)


class WindowManager:
    """
    Manages sliding time windows for flow aggregation
    Calculates statistics needed for aggregation rules
    """
    
    def __init__(self, window_configs: Dict):
        """
        Initialize windows based on configuration
        
        Args:
            window_configs: Dict of window configurations from rules.yaml
        """
        self.windows = {}
        
        for name, config in window_configs.items():
            if config.get('enabled', True):
                size = config['size']
                self.windows[name] = {
                    'size': size,
                    'flows': deque(),
                    'stats': {}
                }
                logger.info(f"Created window '{name}': {size}s")
    
    def add_flow(self, flow_data: Dict):
        """Add a flow to all windows"""
        timestamp = datetime.now()
        
        for window_name, window in self.windows.items():
            window['flows'].append({
                'data': flow_data,
                'timestamp': timestamp
            })
            
            self._cleanup_window(window)
    
    def _cleanup_window(self, window: Dict):
        """Remove flows outside the time window"""
        cutoff_time = datetime.now() - timedelta(seconds=window['size'])
        
        while window['flows'] and window['flows'][0]['timestamp'] < cutoff_time:
            window['flows'].popleft()
    
    def get_statistics(self, window_name: str = 'medium') -> Dict:
        """
        Calculate statistics for a specific window
        
        Returns dict with metrics needed for aggregation rules:
        - syn_flag_count
        - syn_ack_ratio
        - udp_packet_count
        - icmp_packet_count
        - flows_per_ip
        - packets_per_ip
        - unique_dst_ports
        - unique_dst_ports_per_ip
        """
        if window_name not in self.windows:
            logger.warning(f"Window '{window_name}' not found")
            return {}
        
        window = self.windows[window_name]
        self._cleanup_window(window)
        
        flows = [f['data'] for f in window['flows']]
        
        if not flows:
            return {}
        
        stats = {
            'total_flows': len(flows),
            'syn_flag_count': 0,
            'ack_flag_count': 0,
            'udp_packet_count': 0,
            'icmp_packet_count': 0,
            'tcp_packet_count': 0,
            'unique_src_ips': set(),
            'unique_dst_ports': set(),
            'flows_by_ip': defaultdict(int),
            'packets_by_ip': defaultdict(int),
            'dst_ports_by_ip': defaultdict(set),
        }
        
        for flow in flows:
            src_ip = flow.get('src_ip', 'unknown')
            protocol = flow.get('protocol', 0)
            
            stats['unique_src_ips'].add(src_ip)
            stats['flows_by_ip'][src_ip] += 1
            
            fwd_pkts = flow.get('tot_fwd_pkts', 0)
            bwd_pkts = flow.get('tot_bwd_pkts', 0)
            total_pkts = fwd_pkts + bwd_pkts
            stats['packets_by_ip'][src_ip] += total_pkts
            
            dst_port = flow.get('dst_port')
            if dst_port:
                stats['unique_dst_ports'].add(dst_port)
                stats['dst_ports_by_ip'][src_ip].add(dst_port)
            
            if protocol == 6:  # TCP
                stats['tcp_packet_count'] += total_pkts
                stats['syn_flag_count'] += flow.get('syn_flag_cnt', 0)
                stats['ack_flag_count'] += flow.get('ack_flag_cnt', 0)
            elif protocol == 17:  # UDP
                stats['udp_packet_count'] += total_pkts
            elif protocol == 1:  # ICMP
                stats['icmp_packet_count'] += total_pkts
        
        total_syn_ack = stats['syn_flag_count'] + stats['ack_flag_count']
        stats['syn_ack_ratio'] = (
            stats['syn_flag_count'] / total_syn_ack 
            if total_syn_ack > 0 else 0
        )
        
        stats['total_packets'] = (
            stats['tcp_packet_count'] + 
            stats['udp_packet_count'] + 
            stats['icmp_packet_count']
        )
        
        if stats['flows_by_ip']:
            stats['flows_per_ip'] = max(stats['flows_by_ip'].values())
            stats['packets_per_ip'] = max(stats['packets_by_ip'].values())
            stats['unique_dst_ports_per_ip'] = max(
                len(ports) for ports in stats['dst_ports_by_ip'].values()
            )
        else:
            stats['flows_per_ip'] = 0
            stats['packets_per_ip'] = 0
            stats['unique_dst_ports_per_ip'] = 0
        
        stats['unique_src_ips'] = len(stats['unique_src_ips'])
        stats['unique_dst_ports'] = len(stats['unique_dst_ports'])
        
        del stats['flows_by_ip']
        del stats['packets_by_ip']
        del stats['dst_ports_by_ip']
        
        return stats
    
    def get_top_attackers(self, window_name: str = 'medium', top_n: int = 5) -> List[Dict]:
        """Get top N IPs by flow count"""
        if window_name not in self.windows:
            return []
        
        window = self.windows[window_name]
        self._cleanup_window(window)
        
        flows_by_ip = defaultdict(int)
        for flow_entry in window['flows']:
            src_ip = flow_entry['data'].get('src_ip', 'unknown')
            flows_by_ip[src_ip] += 1
        
        sorted_ips = sorted(
            flows_by_ip.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]
        
        return [
            {'ip': ip, 'flow_count': count}
            for ip, count in sorted_ips
        ]
