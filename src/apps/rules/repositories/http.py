import httpx
from datetime import timedelta
import logging

from apps.rules.repositories.base import TelemetryRepository
from apps.rules.utils.rule_engine_utils import TelemetryEvent, map_telemetry_json_to_event

logger = logging.getLogger(__name__)


class HttpTelemetryRepository(TelemetryRepository):
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def _get_window(self, telemetry: TelemetryEvent, minutes: int):
        end = telemetry.timestamp
        start = end - timedelta(minutes=minutes)
        return start, end

    def get_in_window(self, telemetry: TelemetryEvent, minutes: int) -> list[TelemetryEvent]:
        start, end = self._get_window(telemetry, minutes)

        try:
            response = httpx.get(
                f"{self.base_url}/api/telemetry/",
                headers=self.headers,
                params={
                    "device_serial_id": telemetry.device_serial_id,
                    "device_metric_id": telemetry.device_metric_id,
                    "ts_from": start.isoformat(),
                    "ts_to": end.isoformat(),
                },
                timeout=5.0,
            )
            response.raise_for_status()

        except httpx.TimeoutException:
            logger.error("Telemetry API timeout for device %s", telemetry.device_serial_id)
            return []
        except httpx.HTTPStatusError as e:
            logger.error("Telemetry API error: %s", e.response.status_code)
            return []

        return [map_telemetry_json_to_event(item) for item in response.json()]
