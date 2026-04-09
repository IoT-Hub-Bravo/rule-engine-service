import pytest
from unittest.mock import patch, ANY
from datetime import timedelta
from django.core.cache import caches
import uuid
from unittest.mock import MagicMock
from datetime import datetime, timezone

# from apps.users.models import User # ЩО З ЦИМ РОБИТИ
# from apps.devices.models import Device, Metric, DeviceMetric, Telemetry # ЩО З ЦИМ РОБИТИ
from apps.rules.models import Rule
from apps.rules.services.rule_processor import RuleProcessor
from apps.rules.services.condition_evaluator import ConditionEvaluator

from apps.rules.utils.rule_engine_utils import TelemetryEvent

# from apps.rules.services.action import Action # ЩО З ЦИМ РОБИТИ
# from apps.rules.utils.rule_engine_utils import PostgresTelemetryRepository # ЩО З ЦИМ РОБИТИ
from apps.rules.services.condition_evaluator import (
    BooleanEvaluator,
    StringMatchEvaluator,
    EvaluationContext,
)


# ============================================================================
# Helpers
# ============================================================================


def make_context(value, telemetries_in_window=None):
    telemetry = MagicMock()
    telemetry.value = value
    return EvaluationContext(
        telemetry=telemetry,
        telemetries_in_window=telemetries_in_window or [],
    )


def none_context():
    return EvaluationContext(telemetry=None, telemetries_in_window=[])


# ============================================================================
# Factories
# ============================================================================


class TelemetryFactory:
    """
    device_metric — тепер dict {"device_metric_id": int, ...}
    Повертає TelemetryEvent замість Telemetry.objects.create()
    API (сигнатури) — ті самі, що були раніше.
    """

    @staticmethod
    def create(device_metric: dict, value, ts=None) -> TelemetryEvent:
        return TelemetryEvent(
            device_serial_id=f"device-{device_metric['device_metric_id']}",
            value=value,
            timestamp=ts or datetime.now(tz=timezone.utc),
            device_metric_id=device_metric["device_metric_id"],
        )

    @staticmethod
    def create_batch(device_metric: dict, values: list, minutes_ago: int = 1) -> list:
        now = datetime.now(tz=timezone.utc)
        return [
            TelemetryEvent(
                device_serial_id=f"device-{device_metric['device_metric_id']}",
                value=value,
                timestamp=now - timedelta(minutes=minutes_ago) + timedelta(seconds=i),
                device_metric_id=device_metric["device_metric_id"],
            )
            for i, value in enumerate(values)
        ]


class RuleFactory:
    """
    device_metric — тепер dict {"device_metric_id": int, ...}
    Rule.objects.create() залишається — Rule це єдина локальна модель.
    API — той самий.
    """

    @staticmethod
    def create(
        device_metric: dict,
        condition: dict,
        action: str = "notify",
        is_active: bool = True,
        name: str = None,
    ) -> Rule:
        if name is None:
            name = f"Rule-{uuid.uuid4()}"
        return Rule.objects.create(
            name=name,
            device_metric_id=device_metric["device_metric_id"],
            condition=condition,
            action=action,
            is_active=is_active,
        )

    @staticmethod
    def threshold(device_metric: dict, operator: str = ">", value=100, **kwargs) -> Rule:
        return RuleFactory.create(
            device_metric, ConditionFactory.threshold(operator=operator, value=value), **kwargs
        )

    @staticmethod
    def rate(device_metric: dict, count: int = 3, duration_minutes: int = 5, **kwargs) -> Rule:
        return RuleFactory.create(
            device_metric,
            ConditionFactory.rate(count=count, duration_minutes=duration_minutes),
            **kwargs,
        )

    @staticmethod
    def composite(
        device_metric: dict, operator: str = "AND", conditions: list = None, **kwargs
    ) -> Rule:
        return RuleFactory.create(
            device_metric,
            ConditionFactory.composite(operator=operator, conditions=conditions),
            **kwargs,
        )


class ConditionFactory:
    @staticmethod
    def threshold(operator: str = ">", value=100) -> dict:
        return {"type": "threshold", "operator": operator, "value": value}

    @staticmethod
    def rate(count: int = 3, duration_minutes: int = 5) -> dict:
        return {"type": "rate", "count": count, "duration_minutes": duration_minutes}

    @staticmethod
    def composite(operator: str = "AND", conditions: list = None) -> dict:
        return {
            "type": "composite",
            "operator": operator,
            "conditions": conditions
            or [
                ConditionFactory.threshold(operator=">", value=90),
                ConditionFactory.rate(count=3, duration_minutes=5),
            ],
        }


# ============================================================================
# Fixtures — Infrastructure
# ============================================================================


# @pytest.fixture(autouse=True)
# def force_postgres_repository():
#     with patch(
#         "apps.rules.services.rule_processor.choose_repository",
#         return_value=PostgresTelemetryRepository(),
#     ):
#         yield


@pytest.fixture(autouse=True)
def clear_rules_cache():
    from django.test.utils import override_settings
    import django.conf

    with override_settings(
        CACHES={
            **{k: v for k, v in django.conf.settings.CACHES.items() if k != "rules"},
            "rules": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
        }
    ):
        caches["rules"].clear()
        yield


# ============================================================================
# Fixtures — device_metric (раніше були User/Device/Metric/DeviceMetric)
# Імена фікстур — ті самі, що передаються в тести.
# ============================================================================


@pytest.fixture
def device_metric_temperature() -> dict:
    """Замінює ланцюжок user → device → temperature_metric → DeviceMetric."""
    return {"device_metric_id": 1, "device_id": 1, "metric_id": 10}


@pytest.fixture
def device_metric_humidity() -> dict:
    """Замінює ланцюжок user → other_device → humidity_metric → DeviceMetric."""
    return {"device_metric_id": 2, "device_id": 2, "metric_id": 20}


# ============================================================================
# Fixtures — Services
# ============================================================================


@pytest.fixture
def rule_processor():
    return RuleProcessor()


@pytest.fixture
def condition_evaluator():
    return ConditionEvaluator()


# ============================================================================
# Fixtures — Telemetry
# ============================================================================


@pytest.fixture
def high_temperature_telemetry(device_metric_temperature):
    return TelemetryFactory.create(device_metric_temperature, value=111)


@pytest.fixture
def low_temperature_telemetry(device_metric_temperature):
    return TelemetryFactory.create(device_metric_temperature, value=80)


@pytest.fixture
def high_humidity_telemetry(device_metric_humidity):
    return TelemetryFactory.create(device_metric_humidity, value=60)


@pytest.fixture
def low_humidity_telemetry(device_metric_humidity):
    return TelemetryFactory.create(device_metric_humidity, value=20)


# ============================================================================
# Fixtures — Rules
# ============================================================================


@pytest.fixture
def temperature_threshold_rule(device_metric_temperature):
    return RuleFactory.threshold(device_metric_temperature, operator=">", value=100)


@pytest.fixture
def humidity_threshold_rule(device_metric_humidity):
    return RuleFactory.threshold(device_metric_humidity, operator=">", value=50)


# ============================================================================
# Fixtures — Rate Rule Scenarios
# ============================================================================


@pytest.fixture
def rate_rule_count_met(device_metric_temperature):
    telemetries = TelemetryFactory.create_batch(device_metric_temperature, [100, 105, 110])
    rule = RuleFactory.rate(device_metric_temperature, count=3, duration_minutes=5)
    return rule, telemetries[-1]


@pytest.fixture
def rate_rule_count_not_met(device_metric_temperature):
    telemetries = TelemetryFactory.create_batch(device_metric_temperature, [100, 105])
    rule = RuleFactory.rate(device_metric_temperature, count=3, duration_minutes=5)
    return rule, telemetries[-1]


# ============================================================================
# Fixtures — Composite Rule Scenarios
# ============================================================================


@pytest.fixture
def composite_and_rule_all_true(device_metric_temperature):
    telemetries = TelemetryFactory.create_batch(device_metric_temperature, [100, 95, 99])
    rule = RuleFactory.composite(device_metric_temperature, operator="AND")
    return rule, telemetries[-1]


@pytest.fixture
def composite_and_rule_threshold_false(device_metric_temperature):
    telemetries = TelemetryFactory.create_batch(device_metric_temperature, [20, 10, 9])
    rule = RuleFactory.composite(device_metric_temperature, operator="AND")
    return rule, telemetries[-1]


@pytest.fixture
def composite_or_rule_one_true(device_metric_temperature):
    telemetries = TelemetryFactory.create_batch(device_metric_temperature, [100, 95])
    rule = RuleFactory.composite(device_metric_temperature, operator="OR")
    return rule, telemetries[-1]


# ============================================================================
# Fixtures — Mocks
# ============================================================================


# @pytest.fixture
# def mock_action():
#     with patch.object(Action, "dispatch_action") as mock:
#         yield mock


@pytest.fixture
def mock_eval_and_dispatch():
    with (
        patch.object(ConditionEvaluator, "evaluate") as mock_eval,
        # patch.object(Action, "dispatch_action") as mock_dispatch,
    ):
        yield {
            "eval": mock_eval,
        }  # "dispatch": mock_dispatch


# ============================================================================
# Tests — RuleProcessor wiring
# ============================================================================


@pytest.mark.django_db
def test_rule_processor_calls_evaluate_and_dispatch(
    rule_processor, device_metric_temperature, mock_eval_and_dispatch, high_temperature_telemetry
):
    """RuleProcessor should call evaluate and dispatch_action when condition is met."""
    RuleFactory.threshold(device_metric_temperature)
    mock_eval_and_dispatch["eval"].return_value = True

    rule_processor.run(high_temperature_telemetry)

    assert mock_eval_and_dispatch["eval"].called
    assert mock_eval_and_dispatch["dispatch"].called


# ============================================================================
# Tests — Threshold rules
# ============================================================================


@pytest.mark.django_db
def test_threshold_triggers_action_when_exceeded(
    rule_processor, temperature_threshold_rule, high_temperature_telemetry, mock_action
):
    rule_processor.run(high_temperature_telemetry)

    mock_action.assert_called_once_with(temperature_threshold_rule, ANY)


@pytest.mark.django_db
def test_threshold_no_action_when_not_exceeded(
    rule_processor, temperature_threshold_rule, low_temperature_telemetry, mock_action
):
    rule_processor.run(low_temperature_telemetry)

    mock_action.assert_not_called()


@pytest.mark.django_db
def test_threshold_only_matches_own_device_metric(
    rule_processor, high_humidity_telemetry, temperature_threshold_rule, mock_action
):
    """Rule must not fire for telemetry from a different device_metric."""
    rule_processor.run(high_humidity_telemetry)

    mock_action.assert_not_called()


@pytest.mark.django_db
def test_threshold_works_with_float_values(device_metric_temperature, rule_processor, mock_action):
    telemetry = TelemetryFactory.create(device_metric_temperature, 25.7)
    rule = RuleFactory.threshold(device_metric_temperature, operator=">", value=25.5)

    rule_processor.run(telemetry)

    mock_action.assert_called_once_with(rule, ANY)


@pytest.mark.django_db
def test_threshold_works_with_negative_values(
    device_metric_temperature, rule_processor, mock_action
):
    telemetry = TelemetryFactory.create(device_metric_temperature, -10)
    rule = RuleFactory.threshold(device_metric_temperature, operator="<", value=-5)

    rule_processor.run(telemetry)

    mock_action.assert_called_once_with(rule, ANY)


@pytest.mark.django_db
def test_threshold_invalid_operator_does_not_trigger(
    rule_processor, device_metric_temperature, high_temperature_telemetry, mock_action
):
    RuleFactory.create(
        device_metric_temperature,
        ConditionFactory.threshold(operator="INVALID"),
    )

    rule_processor.run(high_temperature_telemetry)

    mock_action.assert_not_called()


@pytest.mark.django_db
def test_inactive_threshold_rule_does_not_trigger(
    rule_processor, device_metric_temperature, high_temperature_telemetry, mock_action
):
    RuleFactory.threshold(device_metric_temperature, is_active=False)

    rule_processor.run(high_temperature_telemetry)

    mock_action.assert_not_called()


# ============================================================================
# Tests — Rate rules
# ============================================================================


@pytest.mark.django_db
def test_rate_triggers_action_when_count_met(rule_processor, rate_rule_count_met, mock_action):
    rule, latest_telemetry = rate_rule_count_met

    rule_processor.run(latest_telemetry)

    mock_action.assert_called_once_with(rule, ANY)


@pytest.mark.django_db
def test_rate_no_action_when_count_not_met(rule_processor, rate_rule_count_not_met, mock_action):
    _, latest_telemetry = rate_rule_count_not_met

    rule_processor.run(latest_telemetry)

    mock_action.assert_not_called()


# ============================================================================
# Tests — Composite rules
# ============================================================================


@pytest.mark.django_db
def test_composite_and_triggers_when_all_conditions_true(
    rule_processor, composite_and_rule_all_true, mock_action
):
    rule, latest_telemetry = composite_and_rule_all_true

    rule_processor.run(latest_telemetry)

    mock_action.assert_called_once_with(rule, ANY)


@pytest.mark.django_db
def test_composite_and_no_action_when_one_condition_false(
    rule_processor, composite_and_rule_threshold_false, mock_action
):
    _, latest_telemetry = composite_and_rule_threshold_false

    rule_processor.run(latest_telemetry)

    mock_action.assert_not_called()


@pytest.mark.django_db
def test_composite_or_triggers_when_at_least_one_condition_true(
    rule_processor, composite_or_rule_one_true, mock_action
):
    rule, latest_telemetry = composite_or_rule_one_true

    rule_processor.run(latest_telemetry)

    mock_action.assert_called_once_with(rule, ANY)


# ============================================================================
# Tests — Unknown / unsupported rule types
# ============================================================================


@pytest.mark.django_db
def test_unknown_rule_type_does_not_trigger(
    rule_processor, device_metric_temperature, high_temperature_telemetry, mock_action
):
    RuleFactory.create(
        device_metric_temperature,
        {"type": "custom", "operator": ">", "value": 100},
    )

    rule_processor.run(high_temperature_telemetry)

    mock_action.assert_not_called()


# ============================================================================
# Tests — Rule condition model parsing
# ============================================================================


@pytest.mark.django_db
def test_rule_stores_threshold_condition_correctly(device_metric_temperature):
    condition = ConditionFactory.threshold(operator=">", value=100)
    rule = RuleFactory.create(device_metric_temperature, condition)

    assert rule.condition == condition


@pytest.mark.django_db
def test_rule_stores_rate_condition_correctly(device_metric_temperature):
    condition = ConditionFactory.rate(count=3, duration_minutes=5)
    rule = RuleFactory.create(device_metric_temperature, condition)

    assert rule.condition == condition


@pytest.mark.django_db
def test_rule_stores_composite_condition_correctly(device_metric_temperature):
    condition = ConditionFactory.composite(
        operator="AND",
        conditions=[
            ConditionFactory.threshold(operator=">", value=90),
            ConditionFactory.rate(count=3, duration_minutes=5),
        ],
    )
    rule = RuleFactory.create(device_metric_temperature, condition)

    assert rule.condition == condition
    assert rule.condition["type"] == "composite"
    assert rule.condition["operator"] == "AND"
    assert len(rule.condition["conditions"]) == 2


# ============================================================================
# Tests — Edge cases
# ============================================================================


@pytest.mark.django_db
def test_threshold_equal_to_boundary_with_gt_operator(
    rule_processor, device_metric_temperature, mock_action
):
    """Value exactly at threshold — '>' should NOT trigger."""
    telemetry = TelemetryFactory.create(device_metric_temperature, value=100)
    RuleFactory.threshold(device_metric_temperature, operator=">", value=100)

    rule_processor.run(telemetry)

    mock_action.assert_not_called()


@pytest.mark.django_db
def test_threshold_equal_to_boundary_with_gte_operator(
    rule_processor, device_metric_temperature, mock_action
):
    """Value exactly at threshold — '>=' should trigger."""
    telemetry = TelemetryFactory.create(device_metric_temperature, value=100)
    rule = RuleFactory.threshold(device_metric_temperature, operator=">=", value=100)

    rule_processor.run(telemetry)

    mock_action.assert_called_once_with(rule, ANY)


@pytest.mark.django_db
def test_threshold_equal_to_boundary_with_lte_operator(
    rule_processor, device_metric_temperature, mock_action
):
    """Value exactly at threshold — '<=' should trigger."""
    telemetry = TelemetryFactory.create(device_metric_temperature, value=100)
    rule = RuleFactory.threshold(device_metric_temperature, operator="<=", value=100)

    rule_processor.run(telemetry)

    mock_action.assert_called_once_with(rule, ANY)


@pytest.mark.django_db
def test_rate_telemetry_outside_duration_not_counted(
    rule_processor, device_metric_temperature, mock_action
):
    """Telemetry older than duration_minutes window should not be counted."""
    TelemetryFactory.create_batch(device_metric_temperature, [100, 105], minutes_ago=10)
    latest = TelemetryFactory.create(device_metric_temperature, value=110)
    RuleFactory.rate(device_metric_temperature, count=2, duration_minutes=5)
    rule_processor.run(latest)

    mock_action.assert_not_called()


# ============================================================================
# Tests — Multiple rules at once
# ============================================================================


@pytest.mark.django_db
def test_multiple_rules_same_device_metric_all_trigger(
    rule_processor, device_metric_temperature, mock_action
):
    """Two active rules on the same device_metric — both should fire."""
    telemetry = TelemetryFactory.create(device_metric_temperature, value=150)
    RuleFactory.threshold(device_metric_temperature, operator=">", value=100)
    RuleFactory.threshold(device_metric_temperature, operator=">", value=120)

    rule_processor.run(telemetry)

    assert mock_action.call_count == 2


@pytest.mark.django_db
def test_multiple_rules_only_matching_triggers(
    rule_processor, device_metric_temperature, mock_action
):
    """Only the rule whose condition is met should fire."""
    telemetry = TelemetryFactory.create(device_metric_temperature, value=110)
    rule_match = RuleFactory.threshold(device_metric_temperature, operator=">", value=100)
    RuleFactory.threshold(device_metric_temperature, operator=">", value=120)

    rule_processor.run(telemetry)

    mock_action.assert_called_once_with(rule_match, ANY)


@pytest.mark.django_db
def test_multiple_rules_mixed_active_inactive(
    rule_processor, device_metric_temperature, high_temperature_telemetry, mock_action
):
    """Active rule fires, inactive rule does not — even when condition is met."""
    active_rule = RuleFactory.threshold(device_metric_temperature, is_active=True)
    RuleFactory.threshold(device_metric_temperature, is_active=False)

    rule_processor.run(high_temperature_telemetry)

    mock_action.assert_called_once_with(active_rule, ANY)


# ============================================================================
# Tests — Rule caching
# ============================================================================


@pytest.mark.django_db
def test_rule_cache_is_used_on_second_call(
    rule_processor, device_metric_temperature, high_temperature_telemetry, mock_action
):
    """Second run() call should read rules from cache, not hit the database again."""
    RuleFactory.threshold(device_metric_temperature)

    with patch("apps.rules.services.rule_processor.Rule.objects.filter") as mock_db_query:
        rule_processor.run(high_temperature_telemetry)
        rule_processor.run(high_temperature_telemetry)

        assert mock_db_query.call_count == 1


@pytest.mark.django_db
def test_cache_invalidated_after_rule_created(
    rule_processor, device_metric_temperature, high_temperature_telemetry, mock_action
):
    """After cache is cleared, a newly created rule should be picked up."""
    rule_processor.run(high_temperature_telemetry)  # warm up cache

    new_rule = RuleFactory.threshold(device_metric_temperature)
    caches["rules"].clear()

    rule_processor.run(high_temperature_telemetry)

    mock_action.assert_called_once_with(new_rule, ANY)


# ============================================================================
# Tests — Errors / exceptions
# ============================================================================


@pytest.mark.django_db
def test_rule_processor_no_rules_does_not_raise(
    rule_processor, high_temperature_telemetry, mock_action
):
    """No rules exist — run() should complete silently without errors."""
    rule_processor.run(high_temperature_telemetry)

    mock_action.assert_not_called()


@pytest.mark.django_db
def test_composite_rule_with_empty_conditions_does_not_trigger(
    rule_processor, device_metric_temperature, high_temperature_telemetry, mock_action
):
    """Composite rule with empty conditions list — should not trigger."""
    RuleFactory.create(
        device_metric_temperature,
        {"type": "composite", "operator": "AND", "conditions": []},
    )

    rule_processor.run(high_temperature_telemetry)

    mock_action.assert_not_called()


# ============================================================================
# Tests — BooleanEvaluator
# ============================================================================


class TestBooleanEvaluator:

    # operator "=="

    def test_equal_true_matches_true(self):
        condition = {"value": True, "operator": "=="}
        assert BooleanEvaluator.evaluate(condition, make_context(True)) is True

    def test_equal_false_matches_false(self):
        condition = {"value": False, "operator": "=="}
        assert BooleanEvaluator.evaluate(condition, make_context(False)) is True

    def test_equal_true_does_not_match_false(self):
        condition = {"value": True, "operator": "=="}
        assert BooleanEvaluator.evaluate(condition, make_context(False)) is False

    def test_equal_false_does_not_match_true(self):
        condition = {"value": False, "operator": "=="}
        assert BooleanEvaluator.evaluate(condition, make_context(True)) is False

    # operator "!="

    def test_not_equal_true_vs_false(self):
        condition = {"value": True, "operator": "!="}
        assert BooleanEvaluator.evaluate(condition, make_context(False)) is True

    def test_not_equal_false_vs_true(self):
        condition = {"value": False, "operator": "!="}
        assert BooleanEvaluator.evaluate(condition, make_context(True)) is True

    def test_not_equal_same_value_does_not_trigger(self):
        condition = {"value": True, "operator": "!="}
        assert BooleanEvaluator.evaluate(condition, make_context(True)) is False

    # default operator (no "operator" key)

    def test_default_operator_is_equal(self):
        condition = {"value": True}  # no "operator" key
        assert BooleanEvaluator.evaluate(condition, make_context(True)) is True

    def test_default_operator_does_not_match_opposite(self):
        condition = {"value": True}
        assert BooleanEvaluator.evaluate(condition, make_context(False)) is False

    # unsupported operator

    def test_unsupported_operator_returns_false(self):
        condition = {"value": True, "operator": ">"}
        assert BooleanEvaluator.evaluate(condition, make_context(True)) is False

    def test_invalid_operator_string_returns_false(self):
        condition = {"value": True, "operator": "INVALID"}
        assert BooleanEvaluator.evaluate(condition, make_context(True)) is False

    # missing / bad value

    def test_missing_value_key_returns_false(self):
        condition = {"operator": "=="}  # no "value"
        assert BooleanEvaluator.evaluate(condition, make_context(True)) is False

    def test_none_telemetry_returns_false(self):
        condition = {"value": True, "operator": "=="}
        assert BooleanEvaluator.evaluate(condition, none_context()) is False

    def test_none_telemetry_not_equal_true_returns_true(self):
        """None != True should be truthy when operator is !=."""
        condition = {"value": True, "operator": "!="}
        assert BooleanEvaluator.evaluate(condition, none_context()) is True


# ============================================================================
# Tests — StringMatchEvaluator
# ============================================================================


class TestStringMatchEvaluator:

    # operator "=="

    def test_equal_matching_strings(self):
        condition = {"value": "active", "operator": "=="}
        assert StringMatchEvaluator.evaluate(condition, make_context("active")) is True

    def test_equal_non_matching_strings(self):
        condition = {"value": "active", "operator": "=="}
        assert StringMatchEvaluator.evaluate(condition, make_context("inactive")) is False

    def test_equal_is_case_sensitive(self):
        condition = {"value": "Active", "operator": "=="}
        assert StringMatchEvaluator.evaluate(condition, make_context("active")) is False

    # operator "!="

    def test_not_equal_different_strings(self):
        condition = {"value": "active", "operator": "!="}
        assert StringMatchEvaluator.evaluate(condition, make_context("inactive")) is True

    def test_not_equal_same_string_does_not_trigger(self):
        condition = {"value": "active", "operator": "!="}
        assert StringMatchEvaluator.evaluate(condition, make_context("active")) is False

    # operator "in"

    def test_in_operator_substring_found(self):
        condition = {"value": "error in stream", "operator": "in"}
        assert StringMatchEvaluator.evaluate(condition, make_context("error")) is True

    def test_in_operator_substring_not_found(self):
        condition = {"value": "all systems go", "operator": "in"}
        assert StringMatchEvaluator.evaluate(condition, make_context("error")) is False

    def test_in_operator_full_match_works(self):
        condition = {"value": "critical", "operator": "in"}
        assert StringMatchEvaluator.evaluate(condition, make_context("critical")) is True

    def test_in_operator_empty_actual_matches_any_expected(self):
        """Empty string is a substring of any string (Python built-in behaviour).
        This may be unexpected business logic - consider validating actual before eval"""
        condition = {"value": "something", "operator": "in"}
        assert StringMatchEvaluator.evaluate(condition, make_context("")) is True

    def test_in_operator_actual_in_empty_string_expected(self):
        """Empty expected string contains empty string, but not non-empty actual."""
        condition = {"value": "", "operator": "in"}
        assert StringMatchEvaluator.evaluate(condition, make_context("anything")) is False

    # default operator (no "operator" key)

    def test_default_operator_is_equal(self):
        condition = {"value": "ok"}  # no "operator" key
        assert StringMatchEvaluator.evaluate(condition, make_context("ok")) is True

    def test_default_operator_does_not_match_different_value(self):
        condition = {"value": "ok"}
        assert StringMatchEvaluator.evaluate(condition, make_context("fail")) is False

    # coercion to string

    def test_numeric_actual_coerced_to_string_for_equal(self):
        condition = {"value": "42", "operator": "=="}
        assert StringMatchEvaluator.evaluate(condition, make_context(42)) is True

    def test_bool_actual_coerced_to_string_for_equal(self):
        condition = {"value": "True", "operator": "=="}
        assert StringMatchEvaluator.evaluate(condition, make_context(True)) is True

    def test_numeric_actual_coerced_for_in_operator(self):
        condition = {"value": "reading 42 sensors", "operator": "in"}
        assert StringMatchEvaluator.evaluate(condition, make_context(42)) is True

    # unsupported operator

    def test_unsupported_operator_returns_false(self):
        condition = {"value": "ok", "operator": ">"}
        assert StringMatchEvaluator.evaluate(condition, make_context("ok")) is False

    def test_invalid_operator_string_returns_false(self):
        condition = {"value": "ok", "operator": "INVALID"}
        assert StringMatchEvaluator.evaluate(condition, make_context("ok")) is False

    # missing / bad value

    def test_missing_value_key_returns_false(self):
        condition = {"operator": "=="}
        assert StringMatchEvaluator.evaluate(condition, make_context("ok")) is False

    def test_none_telemetry_equal_none_string(self):
        """str(None) == 'None' — equality against literal 'None' should pass."""
        condition = {"value": "None", "operator": "=="}
        assert StringMatchEvaluator.evaluate(condition, none_context()) is True

    def test_none_telemetry_not_equal_real_string(self):
        condition = {"value": "active", "operator": "=="}
        assert StringMatchEvaluator.evaluate(condition, none_context()) is False
