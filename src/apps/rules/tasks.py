import requests
import time
from datetime import timedelta
from celery import shared_task, current_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from django.db.models import Q
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction

from apps.rules.services.rule_processor import RuleProcessor
from conf.utils.logging_context import task_id_var, task_name_var

logger_celery = get_task_logger(__name__)


@shared_task
def evaluate_rule(telemetry: dict):
    """Celery task to run RuleProcessor asynchronously on the given telemetry"""
    task_id_var.set(current_task.request.id)
    task_name_var.set(current_task.name)

    start_time = time.perf_counter()

    logger_celery.debug(
        "Task started",
        extra={
            "device_serial_id": telemetry.get("device_serial_id"),
            "device_metric_id": telemetry.get("device_metric_id"),
        },
    )

    try:
        res = RuleProcessor.run(telemetry)

        for eval_res in res.get("results", []):
            if eval_res.get("triggered"):
                publish_audit_event(
                    event=rule_evaluated(
                        rule_id=eval_res.get("rule_id"),
                        details=res.get("telemetry"),
                    )
                )

    except Exception as e:
        logger_celery.error(
            "Task failed",
            extra={
                "device_serial_id": telemetry.get("device_serial_id"),
                "error": str(e),
            },
        )
        raise

    logger_celery.debug(
        "Task finished",
        extra={
            "device_serial_id": telemetry.get("device_serial_id"),
            "duration_seconds": round(time.perf_counter() - start_time, 4),
        },
    )

