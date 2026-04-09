from dataclasses import dataclass
from datetime import datetime
import logging
from enum import Enum

logger = logging.getLogger(__name__)

REDIS_WINDOW_MAX_MINUTES = 60
# Threshold (in minutes) to decide whether to fetch telemetry from:
# - Redis (short-term)
# - PostgreSQL (long-term)

DEFAULT_TELEMETRY_WINDOW_MINUTES = 5
# Default time window (in minutes) for telemetry queries in the rule engine


@dataclass
class TelemetryEvent:
    device_serial_id: str
    value: float | bool | str
    timestamp: datetime
    device_metric_id: int


class NotificationChannels(str, Enum):
    """Enumeration of available notification delivery channels"""

    EMAIL = "email"
    SMS = "sms"


class ActionTypes(str, Enum):
    """Enumeration of available action types"""

    WEBHOOK = "webhook"
    NOTIFICATION = "notification"


###===========
### Mapping
###===========


def map_telemetry_json_to_event(telemetry: dict) -> TelemetryEvent:
    return TelemetryEvent(
        device_serial_id=telemetry.get("device_serial_id"),
        value=telemetry.get("value"),
        timestamp=datetime.fromisoformat(telemetry.get("ts")),
        device_metric_id=telemetry.get("device_metric_id"),
    )
