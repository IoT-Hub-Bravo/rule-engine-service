import json
import pytest
from unittest.mock import patch, MagicMock
from django.test import RequestFactory

from apps.rules.views.rule_views import RuleView, RuleEvaluateView

VIEW = "apps.rules.views.rule_views"

# ─────────────────────── helpers / fixtures ─────────────────────


@pytest.fixture
def factory():
    return RequestFactory()


def make_user(role="user", user_id=1):
    user = MagicMock()
    user.id = user_id
    user.pk = user_id
    user.role = role
    return user


def make_rule(rule_id=1, device_metric_id=10, name="test-rule"):
    rule = MagicMock()
    rule.id = rule_id
    rule.device_metric_id = device_metric_id
    rule.name = name
    rule.description = "desc"
    rule.condition = {}
    rule.action = {}
    rule.is_active = True
    return rule


def json_request(factory, method, path, body=None, user=None, **kwargs):
    fn = getattr(factory, method)
    req = fn(
        path,
        data=json.dumps(body or {}),
        content_type="application/json",
        **kwargs,
    )
    req.user = user or make_user()
    return req


# ════════════════════════ RuleView ═══════════════════════════════

# ─────────────────────── GET single ─────────────────────────────


class TestRuleViewGetSingle:
    def _get(self, factory, rule_id, user=None):
        req = factory.get(f"/rules/{rule_id}/")
        req.user = user or make_user()
        return RuleView.as_view()(req, rule_id=rule_id)

    def test_returns_rule_for_admin(self, factory):
        rule = make_rule()
        with patch(f"{VIEW}.Rule.objects.get", return_value=rule):
            resp = self._get(factory, rule_id=1, user=make_user(role="admin"))

        assert resp.status_code == 200
        assert json.loads(resp.content)["rule"]["id"] == 1

    def test_returns_rule_for_owner(self, factory):
        rule = make_rule(device_metric_id=10)
        with (
            patch(f"{VIEW}.Rule.objects.get", return_value=rule),
            patch(f"{VIEW}.get_user_device_metric_ids", return_value=[10, 20]),
        ):
            resp = self._get(factory, rule_id=1)

        assert resp.status_code == 200

    def test_returns_404_when_not_owner(self, factory):
        rule = make_rule(device_metric_id=99)
        with (
            patch(f"{VIEW}.Rule.objects.get", return_value=rule),
            patch(f"{VIEW}.get_user_device_metric_ids", return_value=[10]),
        ):
            resp = self._get(factory, rule_id=1)

        assert resp.status_code == 404

    def test_returns_404_when_rule_not_found(self, factory):
        from apps.rules.models.rule import Rule

        with patch(f"{VIEW}.Rule.objects.get", side_effect=Rule.DoesNotExist):
            resp = self._get(factory, rule_id=999)

        assert resp.status_code == 404


# ─────────────────────── GET list ───────────────────────────────


class TestRuleViewGetList:
    def _get_list(self, factory, user=None, query=""):
        req = factory.get(f"/rules/{query}")
        req.user = user or make_user()
        return RuleView.as_view()(req)

    def test_admin_gets_all_rules(self, factory):
        rules = [make_rule(i) for i in range(3)]
        qs = MagicMock()
        qs.count.return_value = 3
        qs.__getitem__ = lambda self, s: rules[s]
        with patch(f"{VIEW}.Rule.objects.all", return_value=qs):
            resp = self._get_list(factory, user=make_user(role="admin"))

        assert resp.status_code == 200
        assert json.loads(resp.content)["total"] == 3

    def test_user_gets_only_own_rules(self, factory):
        rules = [make_rule(1, device_metric_id=10)]
        qs = MagicMock()
        qs.count.return_value = 1
        qs.__getitem__ = lambda self, s: rules[s]
        with (
            patch(f"{VIEW}.get_user_device_metric_ids", return_value=[10]),
            patch(f"{VIEW}.Rule.objects.filter", return_value=qs),
        ):
            resp = self._get_list(factory)

        assert resp.status_code == 200

    def test_invalid_limit_returns_400(self, factory):
        resp = self._get_list(factory, query="?limit=abc")
        assert resp.status_code == 400

    def test_invalid_offset_returns_400(self, factory):
        resp = self._get_list(factory, query="?limit=10&offset=xyz")
        assert resp.status_code == 400

    def test_zero_limit_returns_400(self, factory):
        resp = self._get_list(factory, query="?limit=0")
        assert resp.status_code == 400

    def test_negative_offset_returns_400(self, factory):
        resp = self._get_list(factory, query="?limit=10&offset=-1")
        assert resp.status_code == 400

    def test_default_pagination(self, factory):
        qs = MagicMock()
        qs.count.return_value = 0
        qs.__getitem__ = lambda self, s: []
        with patch(f"{VIEW}.Rule.objects.all", return_value=qs):
            resp = self._get_list(factory, user=make_user(role="admin"))

        body = json.loads(resp.content)
        assert body["limit"] == 20
        assert body["offset"] == 0


# ─────────────────────── POST ────────────────────────────────────


class TestRuleViewPost:
    def _post(self, factory, body, user=None):
        return RuleView.as_view()(json_request(factory, "post", "/rules/", body, user))

    def test_creates_rule_for_admin(self, factory):
        rule = make_rule()
        with (
            patch(f"{VIEW}.RuleCreateSerializer") as MockSerializer,
            patch(f"{VIEW}.rule_create", return_value=rule),
            patch(f"{VIEW}.publish_audit_event"),
        ):
            MockSerializer.return_value.is_valid.return_value = True
            MockSerializer.return_value.validated_data = {"device_metric_id": 10}
            resp = self._post(factory, {}, user=make_user(role="admin"))

        assert resp.status_code == 201

    def test_non_admin_without_ownership_returns_403(self, factory):
        with (
            patch(f"{VIEW}.RuleCreateSerializer") as MockSerializer,
            patch(f"{VIEW}.check_device_metric_ownership", return_value=False),
        ):
            MockSerializer.return_value.is_valid.return_value = True
            MockSerializer.return_value.validated_data = {"device_metric_id": 10}
            resp = self._post(factory, {})

        assert resp.status_code == 403

    def test_non_admin_with_ownership_creates_rule(self, factory):
        rule = make_rule()
        with (
            patch(f"{VIEW}.RuleCreateSerializer") as MockSerializer,
            patch(f"{VIEW}.check_device_metric_ownership", return_value=True),
            patch(f"{VIEW}.rule_create", return_value=rule),
            patch(f"{VIEW}.publish_audit_event"),
        ):
            MockSerializer.return_value.is_valid.return_value = True
            MockSerializer.return_value.validated_data = {"device_metric_id": 10}
            resp = self._post(factory, {})

        assert resp.status_code == 201

    def test_invalid_serializer_returns_400(self, factory):
        with patch(f"{VIEW}.RuleCreateSerializer") as MockSerializer:
            MockSerializer.return_value.is_valid.return_value = False
            MockSerializer.return_value.errors = {"name": ["required"]}
            resp = self._post(factory, {})

        assert resp.status_code == 400

    def test_duplicate_name_returns_400(self, factory):
        from django.db import IntegrityError

        with (
            patch(f"{VIEW}.RuleCreateSerializer") as MockSerializer,
            patch(f"{VIEW}.check_device_metric_ownership", return_value=True),
            patch(
                f"{VIEW}.rule_create",
                side_effect=IntegrityError("unique_rule_name_per_device_metric"),
            ),
        ):
            MockSerializer.return_value.is_valid.return_value = True
            MockSerializer.return_value.validated_data = {"device_metric_id": 10}
            resp = self._post(factory, {})

        assert resp.status_code == 400
        assert "already exists" in json.loads(resp.content)["message"]

    def test_invalid_json_returns_400(self, factory):
        req = factory.post("/rules/", data="not json", content_type="application/json")
        req.user = make_user()
        resp = RuleView.as_view()(req)
        assert resp.status_code == 400


# ─────────────────────── PUT ─────────────────────────────────────


class TestRuleViewPut:
    def _put(self, factory, rule_id, body, user=None):
        return RuleView.as_view()(
            json_request(factory, "put", f"/rules/{rule_id}/", body, user),
            rule_id=rule_id,
        )

    def test_full_update_returns_200(self, factory):
        rule = make_rule()
        with (
            patch(f"{VIEW}.Rule.objects.get", return_value=rule),
            patch(f"{VIEW}.RuleCreateSerializer") as MockSerializer,
            patch(f"{VIEW}.rule_put", return_value=rule),
            patch(f"{VIEW}.publish_audit_event"),
        ):
            MockSerializer.return_value.is_valid.return_value = True
            MockSerializer.return_value.validated_data = {}
            resp = self._put(factory, 1, {}, user=make_user(role="admin"))

        assert resp.status_code == 200

    def test_non_owner_gets_404(self, factory):
        rule = make_rule(device_metric_id=99)
        with (
            patch(f"{VIEW}.Rule.objects.get", return_value=rule),
            patch(f"{VIEW}.get_user_device_metric_ids", return_value=[10]),
        ):
            resp = self._put(factory, 1, {})

        assert resp.status_code == 404

    def test_rule_not_found_returns_404(self, factory):
        from apps.rules.models.rule import Rule

        with patch(f"{VIEW}.Rule.objects.get", side_effect=Rule.DoesNotExist):
            resp = self._put(factory, 999, {})

        assert resp.status_code == 404


# ─────────────────────── PATCH ───────────────────────────────────


class TestRuleViewPatch:
    def _patch(self, factory, rule_id, body, user=None):
        return RuleView.as_view()(
            json_request(factory, "patch", f"/rules/{rule_id}/", body, user),
            rule_id=rule_id,
        )

    def test_partial_update_returns_200(self, factory):
        rule = make_rule()
        with (
            patch(f"{VIEW}.Rule.objects.get", return_value=rule),
            patch(f"{VIEW}.RulePatchSerializer") as MockSerializer,
            patch(f"{VIEW}.rule_patch", return_value=rule),
            patch(f"{VIEW}.publish_audit_event"),
        ):
            MockSerializer.return_value.is_valid.return_value = True
            MockSerializer.return_value.validated_data = {}
            resp = self._patch(factory, 1, {}, user=make_user(role="admin"))

        assert resp.status_code == 200
        assert json.loads(resp.content)["rule_id"] == 1

    def test_non_owner_gets_404(self, factory):
        rule = make_rule(device_metric_id=99)
        with (
            patch(f"{VIEW}.Rule.objects.get", return_value=rule),
            patch(f"{VIEW}.get_user_device_metric_ids", return_value=[10]),
        ):
            resp = self._patch(factory, 1, {})

        assert resp.status_code == 404


# ─────────────────────── DELETE ──────────────────────────────────


class TestRuleViewDelete:
    def _delete(self, factory, rule_id, user=None):
        req = factory.delete(f"/rules/{rule_id}/")
        req.user = user or make_user()
        return RuleView.as_view()(req, rule_id=rule_id)

    def test_admin_deletes_rule_returns_204(self, factory):
        rule = make_rule()
        with (
            patch(f"{VIEW}.Rule.objects.get", return_value=rule),
            patch(f"{VIEW}.rule_delete"),
            patch(f"{VIEW}.publish_audit_event"),
        ):
            resp = self._delete(factory, 1, user=make_user(role="admin"))

        assert resp.status_code == 204

    def test_non_owner_gets_404(self, factory):
        rule = make_rule(device_metric_id=99)
        with (
            patch(f"{VIEW}.Rule.objects.get", return_value=rule),
            patch(f"{VIEW}.get_user_device_metric_ids", return_value=[10]),
        ):
            resp = self._delete(factory, 1)

        assert resp.status_code == 404

    def test_not_found_returns_404(self, factory):
        from apps.rules.models.rule import Rule

        with patch(f"{VIEW}.Rule.objects.get", side_effect=Rule.DoesNotExist):
            resp = self._delete(factory, 999)

        assert resp.status_code == 404

    def test_rule_delete_called(self, factory):
        rule = make_rule()
        with (
            patch(f"{VIEW}.Rule.objects.get", return_value=rule),
            patch(f"{VIEW}.rule_delete") as mock_delete,
            patch(f"{VIEW}.publish_audit_event"),
        ):
            self._delete(factory, 1, user=make_user(role="admin"))

        mock_delete.assert_called_once_with(rule_id=1)


# ════════════════════════ RuleEvaluateView ════════════════════════


class TestRuleEvaluateView:
    def _post(self, factory, body, user=None):
        return RuleEvaluateView.as_view()(
            json_request(factory, "post", "/rules/evaluate/", body, user)
        )

    def test_returns_results_for_each_telemetry(self, factory):
        telemetries = [
            {"id": 1, "device_metric_id": 10, "value": 42},
            {"id": 2, "device_metric_id": 10, "value": 55},
        ]
        eval_result = {"triggered": False, "rule_id": None, "telemetry": {}}
        with (
            patch(f"{VIEW}.get_last_telemetries", return_value=telemetries),
            patch(f"{VIEW}.RuleProcessor.run", return_value=eval_result),
            patch(f"{VIEW}.publish_audit_event"),
        ):
            resp = self._post(factory, {})

        body = json.loads(resp.content)
        assert resp.status_code == 200
        assert len(body["results"]) == 2

    def test_telemetry_service_unavailable_returns_503(self, factory):
        import httpx

        with patch(f"{VIEW}.get_last_telemetries", side_effect=httpx.RequestError("down")):
            resp = self._post(factory, {})

        assert resp.status_code == 503

    def test_audit_event_published_when_triggered(self, factory):
        telemetries = [{"id": 1, "device_metric_id": 10, "value": 42}]
        eval_result = {"triggered": True, "rule_id": 5, "telemetry": {"value": 42}}
        with (
            patch(f"{VIEW}.get_last_telemetries", return_value=telemetries),
            patch(f"{VIEW}.RuleProcessor.run", return_value=eval_result),
            patch(f"{VIEW}.publish_audit_event") as mock_audit,
        ):
            self._post(factory, {})

        mock_audit.assert_called_once()

    def test_audit_not_published_when_not_triggered(self, factory):
        telemetries = [{"id": 1, "device_metric_id": 10, "value": 42}]
        eval_result = {"triggered": False, "rule_id": None, "telemetry": {}}
        with (
            patch(f"{VIEW}.get_last_telemetries", return_value=telemetries),
            patch(f"{VIEW}.RuleProcessor.run", return_value=eval_result),
            patch(f"{VIEW}.publish_audit_event") as mock_audit,
        ):
            self._post(factory, {})

        mock_audit.assert_not_called()

    def test_empty_telemetries_returns_empty_results(self, factory):
        with (
            patch(f"{VIEW}.get_last_telemetries", return_value=[]),
            patch(f"{VIEW}.publish_audit_event"),
        ):
            resp = self._post(factory, {})

        assert json.loads(resp.content)["results"] == []

    def test_passes_filters_to_telemetry_service(self, factory):
        with (
            patch(f"{VIEW}.get_last_telemetries", return_value=[]) as mock_get,
            patch(f"{VIEW}.publish_audit_event"),
        ):
            self._post(factory, {"device_id": 7, "device_metric_id": 3})

        _, kwargs = mock_get.call_args
        assert kwargs["device_id"] == 7
        assert kwargs["device_metric_id"] == 3
