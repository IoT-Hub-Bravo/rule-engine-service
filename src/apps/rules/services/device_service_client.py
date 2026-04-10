import httpx
import logging
import time
from django.conf import settings

logger = logging.getLogger("rules")


def _get_with_retry(url: str, params: dict = None, max_retries: int = 3) -> httpx.Response:
    delay = 0.5
    for attempt in range(max_retries):
        try:
            response = httpx.get(url, params=params, timeout=3.0)
            return response
        except httpx.RequestError as e:
            if attempt == max_retries - 1:
                logger.error(f"device-registry unavailable after {max_retries} retries: {e}")
                raise
            logger.warning(f"device-registry attempt {attempt + 1} failed, retrying in {delay}s")
            time.sleep(delay)
            delay *= 2


def get_user_device_metric_ids(user_id: int) -> list[int]:
    """Return all device_metric_ids that belongs to user"""
    try:
        response = _get_with_retry(
            f"{settings.DEVICE_REGISTRY_SERVICE_URL}/device-metrics/"
        )
        response.raise_for_status()
        return response.json().get("device_metric_ids", [])
    except httpx.RequestError as e:
        logger.error(f"device-registry unavailable: {e}")
        raise


def check_device_metric_ownership(device_metric_id: int, user_id: int) -> bool:
    try:
        response = _get_with_retry(
            f"{settings.DEVICE_REGISTRY_URL}/device-metrics/{device_metric_id}/"
        )
        if response.status_code == 404:
            return False
        response.raise_for_status()
        return response.json().get("device_user_id") == user_id
    except httpx.RequestError as e:
        logger.error(f"device-registry unavailable: {e}")
        raise


def check_device_metric_exists(device_metric_id: int) -> bool:
    try:
        response = _get_with_retry(
            f"{settings.DEVICE_REGISTRY_SERVICE_URL}/device-metrics/{device_metric_id}/"
        )
        return response.status_code == 200
    except httpx.RequestError as e:
        logger.error(f"device-registry unavailable: {e}")
        raise