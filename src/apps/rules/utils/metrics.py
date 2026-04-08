"""
Custom Prometheus metrics for IoT Hub ingestion monitoring.

These metrics track:
- Ingestion throughput (messages received/processed)
- Processing latency
- Error rates
- Rule evaluation and event creation

Usage:
    from apps.common.metrics import ingestion_messages_total
    ingestion_messages_total.labels(source='mqtt', status='success').inc()
"""

from prometheus_client import Counter, Histogram

rules_evaluated_total = Counter(
    'iot_rules_evaluated_total',
    'Total number of rules evaluated',
    ['rule_type'],  # threshold, rate, composite, etc
)

rules_triggered_total = Counter(
    'iot_rules_triggered_total',
    'Number of rules that triggered (condition matched)',
    ['rule_type'],
)

rule_processing_seconds = Histogram(
    'iot_rule_processing_seconds',
    'Time to process rules for a telemetry point',
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)