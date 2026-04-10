import pytest
from unittest.mock import MagicMock, patch

MODULE = "apps.rules.consumers.rule_engine"


@pytest.fixture(autouse=True, scope="session")
def _patch_django_and_redis_at_import():
    """
    rule_engine.py calls django.setup() and get_redis_client() at the module level.
    Patch them once for the entire session so that the import doesn't fail.
    """
    mock_redis = MagicMock()
    with (
        patch("django.setup"),
        patch("apps.rules.utils.redis_client.get_redis_client", return_value=mock_redis),
        patch(f"{MODULE}.get_redis_client", return_value=mock_redis),
    ):
        yield

@pytest.fixture
def mock_action():
    return MagicMock()