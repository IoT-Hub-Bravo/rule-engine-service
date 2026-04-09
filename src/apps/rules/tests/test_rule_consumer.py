import signal
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from apps.rules.consumers.rule_engine import RuleEvalHandler, rule_eval_errors_total


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
    with patch("consumer.redis_client", mock_redis):
        yield RuleEvalHandler(mock_rule_runner)


# ─────────────────────── RuleEvalHandler ────────────────────────


class TestRuleEvalHandlerSinglePayload:
    def test_valid_payload_calls_delay(self, handler, mock_rule_runner, valid_payload, mock_redis):
        handler.handle(valid_payload)

        mock_rule_runner.delay.assert_called_once()
        telemetry_arg = mock_rule_runner.delay.call_args[0][0]
        assert telemetry_arg["device_serial_id"] == "SN-001"
        assert telemetry_arg["device_metric_id"] == 42
        assert telemetry_arg["value"] == 3.14

    def test_valid_payload_writes_to_redis(self, handler, mock_redis, valid_payload):
        handler.handle(valid_payload)

        mock_redis.zadd.assert_called_once()
        mock_redis.expire.assert_called_once()

    def test_redis_key_format(self, handler, mock_redis, valid_payload):
        handler.handle(valid_payload)

        key = mock_redis.zadd.call_args[0][0]
        ts = valid_payload["ts"].timestamp()
        expected_key = f"telemetry:SN-001:42:{int(ts)}"
        assert key == expected_key

    def test_redis_expire_uses_ttl(self, handler, mock_redis, valid_payload):
        with patch("consumer.TELEMETRY_KEY_TTL", 7200):
            handler.handle(valid_payload)

        _, ttl_arg = mock_redis.expire.call_args[0]
        assert ttl_arg == 7200

    def test_telemetry_dict_contains_isoformat_ts(self, handler, mock_rule_runner, valid_payload):
        handler.handle(valid_payload)

        telemetry_arg = mock_rule_runner.delay.call_args[0][0]
        assert telemetry_arg["ts"] == valid_payload["ts"].isoformat()

    def test_invalid_payload_increments_error_counter(self, handler, mock_rule_runner):
        before = rule_eval_errors_total._value.get()
        handler.handle({"bad_field": "no_serial_id"})
        after = rule_eval_errors_total._value.get()

        assert after == before + 1
        mock_rule_runner.delay.assert_not_called()

    def test_invalid_payload_does_not_write_redis(self, handler, mock_redis):
        handler.handle({"totally": "wrong"})

        mock_redis.zadd.assert_not_called()

    def test_exception_during_processing_increments_counter(
        self, handler, mock_rule_runner, mock_redis, valid_payload
    ):
        mock_redis.zadd.side_effect = RuntimeError("Redis down")
        before = rule_eval_errors_total._value.get()

        handler.handle(valid_payload)

        after = rule_eval_errors_total._value.get()
        assert after == before + 1
        mock_rule_runner.delay.assert_not_called()

    def test_exception_is_logged(self, handler, mock_redis, valid_payload):
        mock_redis.zadd.side_effect = RuntimeError("boom")

        with patch("consumer.logger") as mock_logger:
            handler.handle(valid_payload)
            mock_logger.exception.assert_called_once()


class TestRuleEvalHandlerBatch:
    def test_list_payload_processes_all_items(
        self, handler, mock_rule_runner, valid_payload, mock_redis
    ):
        payloads = [valid_payload, {**valid_payload, "device_serial_id": "SN-002"}]
        handler.handle(payloads)

        assert mock_rule_runner.delay.call_count == 2

    def test_list_with_one_invalid_skips_it(self, handler, mock_rule_runner, valid_payload):
        payloads = [valid_payload, {"bad": "data"}]
        handler.handle(payloads)

        assert mock_rule_runner.delay.call_count == 1

    def test_empty_list_does_nothing(self, handler, mock_rule_runner, mock_redis):
        handler.handle([])

        mock_rule_runner.delay.assert_not_called()
        mock_redis.zadd.assert_not_called()


# ──────────────────────────── main() ────────────────────────────


class TestMainSignalHandlers:
    def test_sigterm_registered_to_consumer_stop(self):
        mock_consumer = MagicMock()
        mock_consumer_cls = MagicMock(return_value=mock_consumer)

        with (
            patch("consumer.KafkaConsumer", mock_consumer_cls),
            patch("consumer.ConsumerConfig"),
            patch("consumer.evaluate_rule"),
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
            patch("consumer.KafkaConsumer", return_value=mock_consumer),
            patch("consumer.ConsumerConfig"),
            patch("consumer.evaluate_rule"),
            patch("signal.signal"),
        ):
            from apps.rules.consumers.rule_engine import main

            main()

        mock_consumer.start.assert_called_once()
