"""
Rule Engine for DDoS Detection

Evaluates per-flow and aggregation rules against network flows.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import yaml

logger = logging.getLogger(__name__)


@dataclass
class RuleMatch:
    """Result of a rule match"""
    rule_id: str
    name: str
    severity: str
    description: str
    action: str
    matched_conditions: List[str]
    confidence: float = 1.0 # luôn là 1 vì rule engine không có khả năng xác định độ tin cậy


class RuleEngine:
    """
    Evaluates rules against network flows
    Supports both per-flow and aggregation rules
    """
    
    def __init__(self, rules_path: str):
        """Load rules from YAML file"""
        with open(rules_path, 'r') as f:
            rules_config = yaml.safe_load(f)
        
        self.per_flow_rules = rules_config.get('per_flow_rules', [])
        self.aggregation_rules = rules_config.get('aggregation_rules', [])
        self.config = rules_config.get('config', {})
        
        # Filter enabled rules
        self.per_flow_rules = [r for r in self.per_flow_rules if r.get('enabled', True)]
        self.aggregation_rules = [r for r in self.aggregation_rules if r.get('enabled', True)]
        
        logger.info(f"Loaded {len(self.per_flow_rules)} per-flow rules")
        logger.info(f"Loaded {len(self.aggregation_rules)} aggregation rules")
    
    def check_per_flow(self, flow_data: Dict) -> Optional[RuleMatch]:
        """
        Check if a single flow matches any per-flow rules
        
        Args:
            flow_data: Flow dictionary from Kafka
            
        Returns:
            RuleMatch if matched, None otherwise
        """
        for rule in self.per_flow_rules:
            if self._evaluate_per_flow_rule(rule, flow_data):
                matched_conditions = [
                    f"{cond['field']} {cond['operator']} {cond['value']}"
                    for cond in rule['conditions']
                ]
                
                return RuleMatch(
                    rule_id=rule['id'],
                    name=rule['name'],
                    severity=rule['severity'],
                    description=rule['description'],
                    action=rule['action'],
                    matched_conditions=matched_conditions
                )
        
        return None
    
    def check_aggregation(self, window_stats: Dict) -> List[RuleMatch]:
        """
        Check if window statistics match any aggregation rules
        
        Args:
            window_stats: Aggregated statistics from WindowManager
            
        Returns:
            List of RuleMatch objects for all matched rules (can be empty)
        """
        matches = []
        
        for rule in self.aggregation_rules:
            if self._evaluate_aggregation_rule(rule, window_stats):
                matched_conditions = [
                    f"{cond['metric']} {cond['operator']} {cond['value']}"
                    for cond in rule['conditions']
                ]
                
                matches.append(RuleMatch(
                    rule_id=rule['id'],
                    name=rule['name'],
                    severity=rule['severity'],
                    description=rule['description'],
                    action=rule['action'],
                    matched_conditions=matched_conditions
                ))
        
        return matches
    
    def _evaluate_per_flow_rule(self, rule: Dict, flow_data: Dict) -> bool:
        """
        Evaluate all conditions of a per-flow rule
        All conditions must be true (AND logic)
        """
        for condition in rule['conditions']:
            if not self._evaluate_condition(condition, flow_data):
                return False
        return True
    
    def _evaluate_aggregation_rule(self, rule: Dict, stats: Dict) -> bool:
        """
        Evaluate all conditions of an aggregation rule
        All conditions must be true (AND logic)
        """
        for condition in rule['conditions']:
            metric = condition['metric']
            operator = condition['operator']
            value = condition['value']
            
            actual_value = stats.get(metric, 0)
            
            if not self._compare(actual_value, operator, value):
                return False
        
        return True
    
    def _evaluate_condition(self, condition: Dict, flow_data: Dict) -> bool:
        """Evaluate a single condition"""
        field = condition['field']
        operator = condition['operator']
        expected_value = condition['value']
        
        # Get actual value from flow data
        actual_value = flow_data.get(field)
        
        if actual_value is None:
            return False
        
        return self._compare(actual_value, operator, expected_value)
    
    def _compare(self, actual: Any, operator: str, expected: Any) -> bool:
        """
        Compare values based on operator
        
        Supported operators:
        - eq: equal
        - ne: not equal
        - gt: greater than
        - gte: greater than or equal
        - lt: less than
        - lte: less than or equal
        - in: value in list
        """
        try:
            if operator == 'eq':
                return actual == expected
            elif operator == 'ne':
                return actual != expected
            elif operator == 'gt':
                return float(actual) > float(expected)
            elif operator == 'gte':
                return float(actual) >= float(expected)
            elif operator == 'lt':
                return float(actual) < float(expected)
            elif operator == 'lte':
                return float(actual) <= float(expected)
            elif operator == 'in':
                return actual in expected
            else:
                logger.warning(f"Unknown operator: {operator}")
                return False
        except (ValueError, TypeError) as e:
            logger.error(f"Comparison error: {e}")
            return False
