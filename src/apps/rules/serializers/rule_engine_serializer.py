from iot_hub_shared.utils_kit import normalize_str, parse_iso8601_utc
from iot_hub_shared.serializer_kit import JSONSerializer

class RuleEngineSerializer(JSONSerializer):
    """Serializer for validating telemetry data for the rule engine"""

    REQUIRED_FIELDS = {
        'value_jsonb': dict,
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

        # value_jsonb
        value_jsonb = data["value_jsonb"]
        value = value_jsonb.get("v")
        value_type = value_jsonb.get("t")
        if value is None or value_type is None:
            self._errors["value_jsonb"] = "'value_jsonb' must contain 'v' and 't'"
        else:
            validated["value"] = value
            validated["value_type"] = value_type

        # device_metric_id
        validated["device_metric_id"] = data["device_metric_id"]

        # device_serial_id
        validated["device_serial_id"] = normalize_str(data["device_serial_id"])

        if self._errors:
            return None

        return validated
