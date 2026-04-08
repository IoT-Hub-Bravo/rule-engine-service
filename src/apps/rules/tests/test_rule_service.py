import pytest
from unittest.mock import patch, MagicMock, call
from django.core.exceptions import ValidationError, ObjectDoesNotExist

from apps.rules.services.rule_service import rule_create, rule_put, rule_patch, rule_delete


# ─────────────────────── fixtures ───────────────────────────────

@pytest.fixture
def valid_rule_data():
    return {
        "name": "High temp",
        "device_metric_id": 10,
        "condition": {"type": "threshold", "value": 80},
        "action": {"type": "notify"},
        "is_active": True,
    }


def make_rule(**kwargs):
    rule = MagicMock()
    rule.id = kwargs.get("id", 1)
    rule.name = kwargs.get("name", "High temp")
    rule.device_metric_id = kwargs.get("device_metric_id", 10)
    rule.condition = kwargs.get("condition", {})
    rule.action = kwargs.get("action", {})
    rule.is_active = kwargs.get("is_active", True)
    return rule


# ════════════════════════ rule_create ════════════════════════════

class TestRuleCreate:
    def test_creates_and_returns_rule(self, valid_rule_data):
        rule = make_rule()
        with (
            patch("apps.rules.services.rule_service.validate_condition"),
            patch("apps.rules.services.rule_service.validate_action"),
            patch("apps.rules.services.rule_service.Rule.objects.create", return_value=rule),
        ):
            result = rule_create(valid_rule_data)

        assert result is rule

    def test_calls_create_with_correct_fields(self, valid_rule_data):
        rule = make_rule()
        with (
            patch("apps.rules.services.rule_service.validate_condition"),
            patch("apps.rules.services.rule_service.validate_action"),
            patch("apps.rules.services.rule_service.Rule.objects.create", return_value=rule) as mock_create,
        ):
            rule_create(valid_rule_data)

        mock_create.assert_called_once_with(
            name="High temp",
            device_metric_id=10,
            condition={"type": "threshold", "value": 80},
            action={"type": "notify"},
            is_active=True,
        )

    def test_is_active_defaults_to_true(self):
        data = {
            "name": "rule",
            "device_metric_id": 1,
            "condition": {},
            "action": {},
        }
        rule = make_rule()
        with (
            patch("apps.rules.services.rule_service.validate_condition"),
            patch("apps.rules.services.rule_service.validate_action"),
            patch("apps.rules.services.rule_service.Rule.objects.create", return_value=rule) as mock_create,
        ):
            rule_create(data)

        assert mock_create.call_args[1]["is_active"] is True

    def test_validates_condition_before_create(self, valid_rule_data):
        with (
            patch("apps.rules.services.rule_service.validate_condition", side_effect=ValidationError("bad")) as mock_val,
            patch("apps.rules.services.rule_service.validate_action"),
            patch("apps.rules.services.rule_service.Rule.objects.create") as mock_create,
        ):
            with pytest.raises(ValidationError):
                rule_create(valid_rule_data)

        mock_create.assert_not_called()

    def test_validates_action_before_create(self, valid_rule_data):
        with (
            patch("apps.rules.services.rule_service.validate_condition"),
            patch("apps.rules.services.rule_service.validate_action", side_effect=ValidationError("bad")),
            patch("apps.rules.services.rule_service.Rule.objects.create") as mock_create,
        ):
            with pytest.raises(ValidationError):
                rule_create(valid_rule_data)

        mock_create.assert_not_called()


# ════════════════════════ rule_put ═══════════════════════════════

class TestRulePut:
    def test_updates_all_fields(self, valid_rule_data):
        rule = make_rule()
        with (
            patch("apps.rules.services.rule_service.Rule.objects.get", return_value=rule),
            patch("apps.rules.services.rule_service.validate_condition"),
            patch("apps.rules.services.rule_service.validate_action"),
        ):
            result = rule_put(rule_id=1, rule_data=valid_rule_data)

        assert rule.name == "High temp"
        assert rule.device_metric_id == 10
        assert rule.is_active is True
        rule.save.assert_called_once()
        assert result is rule

    def test_raises_if_rule_not_found(self, valid_rule_data):
        from apps.rules.models.rule import Rule
        with patch("apps.rules.services.rule_service.Rule.objects.get", side_effect=Rule.DoesNotExist):
            with pytest.raises(Rule.DoesNotExist):
                rule_put(rule_id=999, rule_data=valid_rule_data)

    def test_invalid_condition_does_not_save(self, valid_rule_data):
        rule = make_rule()
        with (
            patch("apps.rules.services.rule_service.Rule.objects.get", return_value=rule),
            patch("apps.rules.services.rule_service.validate_condition", side_effect=ValidationError("bad")),
            patch("apps.rules.services.rule_service.validate_action"),
        ):
            with pytest.raises(ValidationError):
                rule_put(rule_id=1, rule_data=valid_rule_data)

        rule.save.assert_not_called()

    def test_invalid_action_does_not_save(self, valid_rule_data):
        rule = make_rule()
        with (
            patch("apps.rules.services.rule_service.Rule.objects.get", return_value=rule),
            patch("apps.rules.services.rule_service.validate_condition"),
            patch("apps.rules.services.rule_service.validate_action", side_effect=ValidationError("bad")),
        ):
            with pytest.raises(ValidationError):
                rule_put(rule_id=1, rule_data=valid_rule_data)

        rule.save.assert_not_called()

    def test_is_active_defaults_to_true_when_missing(self):
        rule = make_rule()
        data = {"name": "r", "device_metric_id": 1, "condition": {}, "action": {}}
        with (
            patch("apps.rules.services.rule_service.Rule.objects.get", return_value=rule),
            patch("apps.rules.services.rule_service.validate_condition"),
            patch("apps.rules.services.rule_service.validate_action"),
        ):
            rule_put(rule_id=1, rule_data=data)

        assert rule.is_active is True


# ════════════════════════ rule_patch ═════════════════════════════

class TestRulePatch:
    def test_updates_only_provided_fields(self):
        rule = make_rule(name="old", is_active=False)
        with (
            patch("apps.rules.services.rule_service.Rule.objects.get", return_value=rule),
            patch("apps.rules.services.rule_service.validate_condition"),
        ):
            rule_patch(rule_id=1, rule_data={"name": "new"})

        assert rule.name == "new"
        assert rule.is_active is False  # untouched
        rule.save.assert_called_once()

    def test_does_not_touch_missing_fields(self):
        rule = make_rule(device_metric_id=99)
        with (
            patch("apps.rules.services.rule_service.Rule.objects.get", return_value=rule),
        ):
            rule_patch(rule_id=1, rule_data={"name": "updated"})

        assert rule.device_metric_id == 99

    def test_validates_condition_when_present(self):
        rule = make_rule()
        with (
            patch("apps.rules.services.rule_service.Rule.objects.get", return_value=rule),
            patch("apps.rules.services.rule_service.validate_condition", side_effect=ValidationError("bad")),
        ):
            with pytest.raises(ValidationError):
                rule_patch(rule_id=1, rule_data={"condition": {"type": "bad"}})

        rule.save.assert_not_called()

    def test_skips_condition_validation_when_absent(self):
        rule = make_rule()
        with (
            patch("apps.rules.services.rule_service.Rule.objects.get", return_value=rule),
            patch("apps.rules.services.rule_service.validate_condition") as mock_val,
        ):
            rule_patch(rule_id=1, rule_data={"name": "x"})

        mock_val.assert_not_called()

    def test_validates_action_when_present(self):
        rule = make_rule()
        with (
            patch("apps.rules.services.rule_service.Rule.objects.get", return_value=rule),
            patch("apps.rules.services.rule_service.validate_action", side_effect=ValidationError("bad")),
        ):
            with pytest.raises(ValidationError):
                rule_patch(rule_id=1, rule_data={"action": {"type": "bad"}})

        rule.save.assert_not_called()

    def test_skips_action_validation_when_absent(self):
        rule = make_rule()
        with (
            patch("apps.rules.services.rule_service.Rule.objects.get", return_value=rule),
            patch("apps.rules.services.rule_service.validate_action") as mock_val,
        ):
            rule_patch(rule_id=1, rule_data={"name": "x"})

        mock_val.assert_not_called()

    def test_raises_if_rule_not_found(self):
        from apps.rules.models.rule import Rule
        with patch("apps.rules.services.rule_service.Rule.objects.get", side_effect=Rule.DoesNotExist):
            with pytest.raises(Rule.DoesNotExist):
                rule_patch(rule_id=999, rule_data={"name": "x"})

    def test_empty_patch_still_calls_save(self):
        rule = make_rule()
        with patch("apps.rules.services.rule_service.Rule.objects.get", return_value=rule):
            rule_patch(rule_id=1, rule_data={})

        rule.save.assert_called_once()


# ════════════════════════ rule_delete ════════════════════════════

class TestRuleDelete:
    def test_deletes_existing_rule(self):
        rule = make_rule()
        with patch("apps.rules.services.rule_service.Rule.objects.get", return_value=rule):
            rule_delete(rule_id=1)

        rule.delete.assert_called_once()

    def test_silent_when_rule_not_found(self):
        with patch(
            "apps.rules.services.rule_service.Rule.objects.get",
            side_effect=ObjectDoesNotExist,
        ):
            rule_delete(rule_id=999)  # не повинно кидати

    def test_logs_warning_when_not_found(self):
        with (
            patch("apps.rules.services.rule_service.Rule.objects.get", side_effect=ObjectDoesNotExist),
            patch("apps.rules.services.rule_service.logger") as mock_logger,
        ):
            rule_delete(rule_id=999)

        mock_logger.warning.assert_called_once()