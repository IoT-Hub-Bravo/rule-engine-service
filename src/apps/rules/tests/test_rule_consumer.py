import signal
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

MODULE = "apps.rules.consumers.rule_engine"


# ─────────────────────────── helpers ───────────────────────────


def _make_valid_serializer(payload: dict) -> MagicMock:
    mock_ser = MagicMock()
    mock_ser.is_valid.return_value = True
    mock_ser.validated_data = {
        "device_serial_id": payload.get("device_serial_id"),
        "device_metric_id": payload.get("device_metric_id"),
        "value": payload.get("value"),
        "type": payload.get("value_type"),  # серіалізатор повертає "type", не "value_type"
        "ts": payload.get("ts"),
    }
    return mock_ser


def _make_invalid_serializer() -> MagicMock:
    mock_ser = MagicMock()
    mock_ser.is_valid.return_value = False
    mock_ser.errors = {"device_serial_id": ["This field is required."]}
    return mock_ser


# ─────────────────────────── fixtures ───────────────────────────


@pytest.fixture
def valid_payload():
    return {
        "device_serial_id": "SN-001",
        "device_metric_id": 42,
        "value": 3.14,
        "value_type": "float",
        "ts": datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
    }


@pytest.fixture
def mock_redis():
    return MagicMock()


@pytest.fixture
def mock_rule_runner():
    return MagicMock()


@pytest.fixture
def handler(mock_rule_runner, mock_redis):
    """
    Імпортуємо RuleEvalHandler тут (після session-фікстури),
    та замінюємо модуль-рівневу змінну redis_client на наш mock.
    """
    with patch(f"{MODULE}.redis_client", mock_redis):
        from apps.rules.consumers.rule_engine import RuleEvalHandler

        yield RuleEvalHandler(mock_rule_runner)


@pytest.fixture
def error_counter():
    from apps.rules.consumers.rule_engine import rule_eval_errors_total

    return rule_eval_errors_total


# ─────────────────────── RuleEvalHandler ────────────────────────


class TestRuleEvalHandlerSinglePayload:
    def test_valid_payload_calls_delay(self, handler, mock_rule_runner, valid_payload):
        with patch(f"{MODULE}.RuleEngineSerializer") as mock_ser_cls:
            mock_ser_cls.return_value = _make_valid_serializer(valid_payload)
            handler.handle(valid_payload)

        mock_rule_runner.delay.assert_called_once()
        telemetry_arg = mock_rule_runner.delay.call_args[0][0]
        assert telemetry_arg["device_serial_id"] == "SN-001"
        assert telemetry_arg["device_metric_id"] == 42
        assert telemetry_arg["value"] == 3.14

    def test_valid_payload_writes_to_redis(self, handler, mock_redis, valid_payload):
        with patch(f"{MODULE}.RuleEngineSerializer") as mock_ser_cls:
            mock_ser_cls.return_value = _make_valid_serializer(valid_payload)
            handler.handle(valid_payload)

        mock_redis.zadd.assert_called_once()
        mock_redis.expire.assert_called_once()

    def test_redis_key_format(self, handler, mock_redis, valid_payload):
        with patch(f"{MODULE}.RuleEngineSerializer") as mock_ser_cls:
            mock_ser_cls.return_value = _make_valid_serializer(valid_payload)
            handler.handle(valid_payload)

        key = mock_redis.zadd.call_args[0][0]
        ts = valid_payload["ts"].timestamp()
        assert key == f"telemetry:SN-001:42:{int(ts)}"

    def test_redis_expire_uses_ttl(self, handler, mock_redis, valid_payload):
        with (
            patch(f"{MODULE}.RuleEngineSerializer") as mock_ser_cls,
            patch(f"{MODULE}.TELEMETRY_KEY_TTL", 7200),
        ):
            mock_ser_cls.return_value = _make_valid_serializer(valid_payload)
            handler.handle(valid_payload)

        _, ttl_arg = mock_redis.expire.call_args[0]
        assert ttl_arg == 7200

    def test_telemetry_dict_contains_isoformat_ts(self, handler, mock_rule_runner, valid_payload):
        with patch(f"{MODULE}.RuleEngineSerializer") as mock_ser_cls:
            mock_ser_cls.return_value = _make_valid_serializer(valid_payload)
            handler.handle(valid_payload)

        telemetry_arg = mock_rule_runner.delay.call_args[0][0]
        assert telemetry_arg["ts"] == valid_payload["ts"].isoformat()

    def test_invalid_payload_increments_error_counter(
        self, handler, mock_rule_runner, error_counter
    ):
        before = error_counter._value.get()

        with patch(f"{MODULE}.RuleEngineSerializer") as mock_ser_cls:
            mock_ser_cls.return_value = _make_invalid_serializer()
            handler.handle({"bad_field": "no_serial_id"})

        assert error_counter._value.get() == before + 1
        mock_rule_runner.delay.assert_not_called()

    def test_invalid_payload_does_not_write_redis(self, handler, mock_redis):
        with patch(f"{MODULE}.RuleEngineSerializer") as mock_ser_cls:
            mock_ser_cls.return_value = _make_invalid_serializer()
            handler.handle({"totally": "wrong"})

        mock_redis.zadd.assert_not_called()

    def test_exception_during_processing_increments_counter(
        self, handler, mock_rule_runner, mock_redis, valid_payload, error_counter
    ):
        with patch(f"{MODULE}.RuleEngineSerializer") as mock_ser_cls:
            mock_ser_cls.return_value = _make_valid_serializer(valid_payload)
            mock_redis.zadd.side_effect = RuntimeError("Redis down")

            before = error_counter._value.get()
            handler.handle(valid_payload)

        assert error_counter._value.get() == before + 1
        mock_rule_runner.delay.assert_not_called()

    def test_exception_is_logged(self, handler, mock_redis, valid_payload):
        with (
            patch(f"{MODULE}.RuleEngineSerializer") as mock_ser_cls,
            patch(f"{MODULE}.logger") as mock_logger,
        ):
            mock_ser_cls.return_value = _make_valid_serializer(valid_payload)
            mock_redis.zadd.side_effect = RuntimeError("boom")
            handler.handle(valid_payload)

        mock_logger.exception.assert_called_once()


class TestRuleEvalHandlerBatch:
    def test_list_payload_processes_all_items(
        self, handler, mock_rule_runner, valid_payload, mock_redis
    ):
        payload_2 = {**valid_payload, "device_serial_id": "SN-002"}

        with patch(f"{MODULE}.RuleEngineSerializer") as mock_ser_cls:
            mock_ser_cls.side_effect = [
                _make_valid_serializer(valid_payload),
                _make_valid_serializer(payload_2),
            ]
            handler.handle([valid_payload, payload_2])

        assert mock_rule_runner.delay.call_count == 2

    def test_list_with_one_invalid_skips_it(self, handler, mock_rule_runner, valid_payload):
        with patch(f"{MODULE}.RuleEngineSerializer") as mock_ser_cls:
            mock_ser_cls.side_effect = [
                _make_valid_serializer(valid_payload),
                _make_invalid_serializer(),
            ]
            handler.handle([valid_payload, {"bad": "data"}])

        assert mock_rule_runner.delay.call_count == 1

    def test_empty_list_does_nothing(self, handler, mock_rule_runner, mock_redis):
        handler.handle([])

        mock_rule_runner.delay.assert_not_called()
        mock_redis.zadd.assert_not_called()


# ──────────────────────────── main() ────────────────────────────


class TestMainSignalHandlers:
    def test_sigterm_registered_to_consumer_stop(self):
        mock_consumer = MagicMock()

        with (
            patch(f"{MODULE}.KafkaConsumer", return_value=mock_consumer),
            patch(f"{MODULE}.ConsumerConfig"),
            patch(f"{MODULE}.evaluate_rule"),
            patch("signal.signal") as mock_signal,
        ):
            from apps.rules.consumers.rule_engine import main

            main()

        calls = {c[0][0]: c[0][1] for c in mock_signal.call_args_list}
        assert calls[signal.SIGTERM] == mock_consumer.stop
        assert calls[signal.SIGINT] == mock_consumer.stop

    def test_consumer_start_called(self):
        mock_consumer = MagicMock()

        with (
            patch(f"{MODULE}.KafkaConsumer", return_value=mock_consumer),
            patch(f"{MODULE}.ConsumerConfig"),
            patch(f"{MODULE}.evaluate_rule"),
            patch("signal.signal"),
        ):
            from apps.rules.consumers.rule_engine import main

            main()

        mock_consumer.start.assert_called_once()
