import httpx
import logging
from django.conf import settings

logger = logging.getLogger("rules")


def get_last_telemetries(
    user_id: int,
    is_admin: bool,
    device_id: int | None = None,
    device_metric_id: int | None = None,
) -> list[dict]:
    params = {}
    if device_id is not None:
        params["device_id"] = device_id
    if device_metric_id is not None:
        params["device_metric_id"] = device_metric_id
    if not is_admin:
        params["user_id"] = user_id

    response = httpx.get(
        f"{settings.TELEMETRY_SERVICE_URL}", #### чесно хз
        params=params,
        headers={"X-Internal-Token": settings.INTERNAL_SECRET},
        timeout=5.0,
    )
    response.raise_for_status()
    return response.json().get("items", [])