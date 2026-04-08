import httpx
import logging
from django.conf import settings
from decouple import config

logger = logging.getLogger("rules")

def get_user_device_metric_ids(user_id: int) -> list[int]:
    """Return all device_metric_ids that belongs to user"""
    try:
        response = httpx.get(
            f"{settings.DEVICE_METRIC_SERVICE_URL}", # тут треба подумати
            params={"user_id": user_id},
            headers={"X-Internal-Token": settings.INTERNAL_SECRET},
            timeout=3.0,
        )
        response.raise_for_status()
        return response.json().get("device_metric_ids", [])
    except httpx.RequestError as e:
        logger.error(f"device-service unavailable: {e}")
        raise


def check_device_metric_ownership(device_metric_id: int, user_id: int) -> bool:
    """Check if device_metric belongs to user"""
    try:
        ids = get_user_device_metric_ids(user_id)
        return device_metric_id in ids
    except httpx.RequestError:
        raise