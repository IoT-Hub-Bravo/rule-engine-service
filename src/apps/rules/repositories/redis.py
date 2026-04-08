from datetime import datetime

from apps.rules.repositories.base import TelemetryRepository
from apps.rules.utils.rule_engine_utils import TelemetryEvent


class RedisTelemetryRepository(TelemetryRepository):
    """
    Redis-based implementation of TelemetryRepository

    Assumes telemetry data is stored in Redis Sorted Sets,
    where:
        - key = telemetry:{device_serial_id}:{device_metric_id}:{unix_timestamp}
        - score = Unix timestamp
        - member = metric value (stringified float)
    """

    def __init__(self, redis_client):
        """
        :param redis_client: Initialized Redis client instance
        """
        self.redis = redis_client

    def _parse_value(self, raw: str) -> float | bool | str:
        """Try to parse Redis value to the most appropriate type."""
        if raw.lower() == 'true':
            return True
        if raw.lower() == 'false':
            return False
        try:
            return float(raw)
        except ValueError:
            return raw

    def get_in_window(self, telemetry: TelemetryEvent, minutes: int):
        """
        Retrieve metric values from Redis within the specified time window

        :param telemetry: Incoming telemetry event.
        :param minutes: Window size in minutes.
        :return: List of float metric values within the window.
        """
        key = f"telemetry:{telemetry.device_serial_id}:{telemetry.device_metric_id}:{int(telemetry.timestamp.timestamp())}"

        end_ts = int(telemetry.timestamp.timestamp())
        start_ts = end_ts - minutes * 60

        items = self.redis.zrangebyscore(key, start_ts, end_ts, withscores=True)

        return [
            TelemetryEvent(
                device_serial_id=telemetry.device_serial_id,
                value=self._parse_value(value),
                timestamp=datetime.fromtimestamp(float(score)),
                device_metric_id=telemetry.device_metric_id,
            )
            for value, score in items
        ]
