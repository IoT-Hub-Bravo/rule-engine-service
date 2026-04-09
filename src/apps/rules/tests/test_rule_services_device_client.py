import pytest
import httpx
from unittest.mock import patch, MagicMock
from django.conf import settings

from apps.rules.services.device_service_client import (
    get_user_device_metric_ids,
    check_device_metric_ownership,
)


# ─────────────────────── fixtures ───────────────────────────────


@pytest.fixture
def mock_response():
    def _make(ids: list[int] = None, status_code: int = 200):
        response = MagicMock(spec=httpx.Response)
        response.status_code = status_code
        response.json.return_value = {"device_metric_ids": ids or []}
        if status_code >= 400:
            response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "error", request=MagicMock(), response=response
            )
        else:
            response.raise_for_status.return_value = None
        return response

    return _make


# ──────────────── get_user_device_metric_ids ────────────────────


class TestGetUserDeviceMetricIds:
    def test_returns_ids_on_success(self, mock_response):
        with patch("httpx.get", return_value=mock_response([1, 2, 3])):
            result = get_user_device_metric_ids(user_id=7)

        assert result == [1, 2, 3]

    def test_returns_empty_list_when_key_missing(self, mock_response):
        resp = mock_response()
        resp.json.return_value = {}  # no "device_metric_ids" key
        with patch("httpx.get", return_value=resp):
            result = get_user_device_metric_ids(user_id=7)

        assert result == []

    def test_passes_correct_params(self, mock_response):
        with patch("httpx.get", return_value=mock_response()) as mock_get:
            get_user_device_metric_ids(user_id=7)

        _, kwargs = mock_get.call_args
        assert kwargs["params"] == {"user_id": 7}

    def test_passes_auth_header(self, mock_response):
        with patch("httpx.get", return_value=mock_response()) as mock_get:
            get_user_device_metric_ids(user_id=7)

        _, kwargs = mock_get.call_args
        assert kwargs["headers"]["X-Internal-Token"] == settings.INTERNAL_SECRET

    def test_uses_correct_url(self, mock_response):
        with patch("httpx.get", return_value=mock_response()) as mock_get:
            get_user_device_metric_ids(user_id=7)

        url = mock_get.call_args[0][0]
        assert url == settings.DEVICE_METRIC_SERVICE_URL

    def test_raises_on_request_error(self):
        with patch("httpx.get", side_effect=httpx.RequestError("timeout")):
            with pytest.raises(httpx.RequestError):
                get_user_device_metric_ids(user_id=7)

    def test_logs_on_request_error(self):
        with patch("httpx.get", side_effect=httpx.RequestError("timeout")):
            with patch("apps.rules.repositories.http.logger") as mock_logger:
                with pytest.raises(httpx.RequestError):
                    get_user_device_metric_ids(user_id=7)

        mock_logger.error.assert_called_once()

    def test_raises_on_4xx(self, mock_response):
        with patch("httpx.get", return_value=mock_response(status_code=403)):
            with pytest.raises(httpx.HTTPStatusError):
                get_user_device_metric_ids(user_id=7)

    def test_timeout_value(self, mock_response):
        with patch("httpx.get", return_value=mock_response()) as mock_get:
            get_user_device_metric_ids(user_id=7)

        _, kwargs = mock_get.call_args
        assert kwargs["timeout"] == 3.0


# ──────────────── check_device_metric_ownership ─────────────────


class TestCheckDeviceMetricOwnership:
    def test_returns_true_when_id_in_list(self, mock_response):
        with patch("httpx.get", return_value=mock_response([10, 20, 30])):
            assert check_device_metric_ownership(20, user_id=5) is True

    def test_returns_false_when_id_not_in_list(self, mock_response):
        with patch("httpx.get", return_value=mock_response([10, 20])):
            assert check_device_metric_ownership(99, user_id=5) is False

    def test_returns_false_on_empty_list(self, mock_response):
        with patch("httpx.get", return_value=mock_response([])):
            assert check_device_metric_ownership(1, user_id=5) is False

    def test_propagates_request_error(self):
        with patch("httpx.get", side_effect=httpx.RequestError("down")):
            with pytest.raises(httpx.RequestError):
                check_device_metric_ownership(1, user_id=5)
