import pytest
import httpx
from unittest.mock import patch, MagicMock
from django.conf import settings

from apps.rules.repositories.http import get_last_telemetries


# ─────────────────────── fixtures ───────────────────────────────


@pytest.fixture
def mock_get():
    """Patches httpx.get and returns a configurable mock response"""

    def _make(items=None, status_code=200):
        response = MagicMock(spec=httpx.Response)
        response.json.return_value = {"items": items or []}
        if status_code >= 400:
            response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "error", request=MagicMock(), response=response
            )
        else:
            response.raise_for_status.return_value = None
        return response

    return _make


# ──────────────────────── response handling ─────────────────────


class TestGetLastTelemetriesResponse:
    def test_returns_items_on_success(self, mock_get):
        items = [{"id": 1, "value": 42}]
        with patch("httpx.get", return_value=mock_get(items)):
            result = get_last_telemetries(user_id=1, is_admin=False)

        assert result == items

    def test_returns_empty_list_when_key_missing(self, mock_get):
        resp = mock_get()
        resp.json.return_value = {}
        with patch("httpx.get", return_value=resp):
            result = get_last_telemetries(user_id=1, is_admin=False)

        assert result == []

    def test_raises_on_4xx(self, mock_get):
        with patch("httpx.get", return_value=mock_get(status_code=403)):
            with pytest.raises(httpx.HTTPStatusError):
                get_last_telemetries(user_id=1, is_admin=False)

    def test_raises_on_request_error(self):
        with patch("httpx.get", side_effect=httpx.RequestError("timeout")):
            with pytest.raises(httpx.RequestError):
                get_last_telemetries(user_id=1, is_admin=False)


# ──────────────────────── params building ───────────────────────


class TestGetLastTelemetriesParams:
    def _get_params(self, mock_get, **kwargs):
        with patch("httpx.get", return_value=mock_get()) as m:
            get_last_telemetries(**kwargs)
        return m.call_args[1]["params"]

    def test_admin_does_not_send_user_id(self, mock_get):
        params = self._get_params(mock_get, user_id=5, is_admin=True)
        assert "user_id" not in params

    def test_non_admin_sends_user_id(self, mock_get):
        params = self._get_params(mock_get, user_id=5, is_admin=False)
        assert params["user_id"] == 5

    def test_device_id_included_when_provided(self, mock_get):
        params = self._get_params(mock_get, user_id=1, is_admin=False, device_id=99)
        assert params["device_id"] == 99

    def test_device_id_excluded_when_none(self, mock_get):
        params = self._get_params(mock_get, user_id=1, is_admin=False, device_id=None)
        assert "device_id" not in params

    def test_device_metric_id_included_when_provided(self, mock_get):
        params = self._get_params(mock_get, user_id=1, is_admin=False, device_metric_id=7)
        assert params["device_metric_id"] == 7

    def test_device_metric_id_excluded_when_none(self, mock_get):
        params = self._get_params(mock_get, user_id=1, is_admin=False)
        assert "device_metric_id" not in params

    def test_all_optional_params_combined(self, mock_get):
        params = self._get_params(
            mock_get, user_id=3, is_admin=False, device_id=10, device_metric_id=20
        )
        assert params == {"user_id": 3, "device_id": 10, "device_metric_id": 20}

    def test_admin_with_filters_no_user_id(self, mock_get):
        params = self._get_params(
            mock_get, user_id=3, is_admin=True, device_id=10, device_metric_id=20
        )
        assert params == {"device_id": 10, "device_metric_id": 20}


# ──────────────────────── request config ────────────────────────


class TestGetLastTelemetriesRequest:
    def test_uses_correct_url(self, mock_get):
        with patch("httpx.get", return_value=mock_get()) as m:
            get_last_telemetries(user_id=1, is_admin=False)

        assert m.call_args[0][0] == settings.TELEMETRY_SERVICE_URL

    def test_sends_auth_header(self, mock_get):
        with patch("httpx.get", return_value=mock_get()) as m:
            get_last_telemetries(user_id=1, is_admin=False)

        assert m.call_args[1]["headers"]["X-Internal-Token"] == settings.INTERNAL_SECRET

    def test_timeout_value(self, mock_get):
        with patch("httpx.get", return_value=mock_get()) as m:
            get_last_telemetries(user_id=1, is_admin=False)

        assert m.call_args[1]["timeout"] == 5.0
