import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import caches

from apps.rules.models.rule import Rule

logger = logging.getLogger(__name__)


@receiver([post_save, post_delete], sender=Rule)
@receiver([post_save, post_delete], sender=Rule)
def invalidate_rule_cache(sender, instance, **kwargs):
    try:
        cache_rule = caches["rules"]

        cache_key = f"{instance.device_metric_id}"
        cache_rule.delete(cache_key)

    except Exception:
        logger.exception("Cache invalidation failed")
