import logging
import time
from django.core.cache import caches
from django.conf import settings

from apps.rules.models.rule import Rule
# from apps.rules.services.action import Action
from apps.rules.services.condition_evaluator import EvaluationContext
from apps.rules.services.condition_evaluator import ConditionEvaluator
from apps.rules.repositories.http import HttpTelemetryRepository
from apps.rules.repositories.redis import RedisTelemetryRepository
from apps.rules.repositories.base import TelemetryRepository
from apps.rules.utils.redis_client import get_redis_client
from apps.rules.utils.metrics import (
    rules_evaluated_total,
    rules_triggered_total,
    rule_processing_seconds,
)
from apps.rules.utils.rule_engine_utils import (
    map_telemetry_json_to_event,
    DEFAULT_TELEMETRY_WINDOW_MINUTES,
    REDIS_WINDOW_MAX_MINUTES,
    TelemetryEvent,
)


logger = logging.getLogger(__name__)
redis_client = get_redis_client()


class TelemetryMapper:
    """Maps raw telemetry input (Telemetry model, dict, or TelemetryEvent) to TelemetryEvent"""

    def __init__(self, telemetry: dict | TelemetryEvent):
        self.telemetry = telemetry

    def map(self) -> TelemetryEvent:
        if isinstance(self.telemetry, dict):
            return map_telemetry_json_to_event(self.telemetry)
        elif isinstance(self.telemetry, TelemetryEvent):
            return self.telemetry
        raise TypeError(f"Unsupported telemetry type: {type(self.telemetry)}")


class RuleCache:
    """Fetches and caches active rules for a given telemetry device and metric"""

    def __init__(self, telemetry: TelemetryEvent):
        self.telemetry = telemetry

    def get_rules(self) -> list[Rule]:
        cache = caches["rules"]
        cache_key = f"{self.telemetry.device_serial_id}:{self.telemetry.device_metric_id}"

        rules = cache.get(cache_key)
        if rules is None:
            rules = list(
                Rule.objects.filter(
                    is_active=True,
                    device_metric_id=self.telemetry.device_metric_id,
                )
            )
            cache.set(cache_key, rules, timeout=settings.RULES_CACHE_TTL)
        return rules


def choose_repository(duration_minutes: int) -> TelemetryRepository:
    """
    Return the appropriate telemetry repository based on the query duration
    Uses Redis for short windows (<= REDIS_WINDOW_MAX_MINUTES) and PostgreSQL for longer ones
    """
    if duration_minutes > REDIS_WINDOW_MAX_MINUTES:
        logger.debug("Using PostgreSQL repository", extra={"duration_minutes": duration_minutes})
        return HttpTelemetryRepository()
    logger.debug("Using Redis repository", extra={"duration_minutes": duration_minutes})
    return RedisTelemetryRepository(redis_client)


def get_window(telemetry: TelemetryEvent, duration_minutes: int) -> list[TelemetryEvent]:
    """Get list of telemetries for that time window"""
    repository = choose_repository(duration_minutes)
    return repository.get_in_window(telemetry, duration_minutes)


class RuleProcessor:
    """
    Processes active rules for a given telemetry and triggers actions if conditions match.
    Collects Prometheus metrics for monitoring rule evaluation performance.
    """

    @staticmethod
    def run(telemetry: dict) -> dict:
        """
        Returns a dict with triggered rules for this telemetry.
        Tracks: rules evaluated, rules triggered, processing time.
        """
        start_time = time.perf_counter()
        results = []

        mapped_telemetry = TelemetryMapper(telemetry=telemetry).map()
        logger.debug(
            "Telemetry mapped",
            extra={
                "device_serial_id": mapped_telemetry.device_serial_id,
                "device_metric_id": mapped_telemetry.device_metric_id,
            },
        )

        rules = RuleCache(telemetry=mapped_telemetry).get_rules()  # get rules from cache

        for rule in rules:
            condition = rule.condition
            rule_type = condition.get("type", "unknown")
            logger.debug("Evaluating rule", extra={"rule_id": rule.id, "rule_type": rule_type})

            rules_evaluated_total.labels(rule_type=rule_type).inc()
            duration_minutes = condition.get("duration_minutes", DEFAULT_TELEMETRY_WINDOW_MINUTES)

            telemetry_window = get_window(mapped_telemetry, duration_minutes)

            if ConditionEvaluator.evaluate(
                condition,
                context=EvaluationContext(
                    telemetry=mapped_telemetry, telemetries_in_window=telemetry_window
                ),
            ):
                rules_triggered_total.labels(rule_type=rule_type).inc()
                logger.debug(
                    "Rule triggered - dispatching action",
                    extra={"rule_id": rule.id, "rule_type": rule_type},
                )
                # Action.dispatch_action(rule, mapped_telemetry)
                results.append({"rule_id": rule.id, "triggered": True})
            else:
                logger.debug(
                    "Rule not triggered",
                    extra={"rule_id": rule.id, "rule_type": rule_type},
                )
                results.append({"rule_id": rule.id, "triggered": False})

        duration = time.perf_counter() - start_time
        rule_processing_seconds.observe(duration)

        return {
            "telemetry": {
                "device_serial_id": mapped_telemetry.device_serial_id,
                "value": mapped_telemetry.value,
                "timestamp": mapped_telemetry.timestamp,
            },
            "results": results,
        }
