from typing import Any

from iot_hub_shared.utils_kit import normalize_str, parse_iso8601_utc
from iot_hub_shared.serializer_kit import JSONSerializer


class RuleEngineSerializer(JSONSerializer):
    """Serializer for validating telemetry data for the rule engine"""

    REQUIRED_FIELDS = {
        'type': str,
        'value': (int, float, bool, str),
        'ts': str,
        'device_metric_id': int,
        'device_serial_id': str,
    }

    def _validate_fields(self, data):
        validated = {}

        # ts
        try:
            ts = parse_iso8601_utc(data["ts"])
            validated["ts"] = ts
        except Exception:
            self._errors["ts"] = "Invalid datetime format"

        # type + value
        value_type = data.get("type")
        value = data.get("value")

        if value_type not in ("numeric", "string", "boolean"):
            self._errors["type"] = "Invalid type"
        else:
            is_valid = True

            if value_type == "numeric" and not isinstance(value, (int, float)):
                self._errors["value"] = "Must be int or float"
                is_valid = False

            elif value_type == "string" and not isinstance(value, str):
                self._errors["value"] = "Must be string"
                is_valid = False

            elif value_type == "boolean" and not isinstance(value, bool):
                self._errors["value"] = "Must be boolean"
                is_valid = False

            if is_valid:
                validated["value"] = value
                validated["value_type"] = value_type

        # device_metric_id
        validated["device_metric_id"] = data["device_metric_id"]

        # device_serial_id
        validated["device_serial_id"] = normalize_str(data["device_serial_id"])

        if self._errors:
            return None

        return validated
