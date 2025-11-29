import pathlib
import sys

import pytest
from pydantic import ValidationError

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.extend([str(REPO_ROOT / "api" / "src"), str(REPO_ROOT / "pipelines" / "src")])

from ragtrader_api.strategy.schema import (  # noqa: E402
    ExitRule,
    StrategySchema,
    validate_strategy_payload,
)


def _valid_payload():
    return {
        "instrument": "AAPL",
        "sentiment_zscore": 1.5,
        "lead_lag": 3,
        "action": "long",
        "atr_stop": 2.0,
        "size_fraction": 0.25,
        "exits": [{"kind": "take_profit", "value": 1.8}],
    }


def test_valid_strategy_schema_accepts_expected_payload():
    payload = _valid_payload()

    result = validate_strategy_payload(payload)

    assert isinstance(result, StrategySchema)
    assert result.instrument == "AAPL"
    assert result.action == "long"
    assert result.exits == [ExitRule(kind="take_profit", value=1.8)]


def test_strategy_schema_requires_all_keys():
    payload = _valid_payload()
    payload.pop("sentiment_zscore")

    with pytest.raises(ValidationError):
        validate_strategy_payload(payload)


def test_strategy_schema_rejects_undefined_fields():
    payload = _valid_payload()
    payload["drop_tables"] = True

    with pytest.raises(ValidationError):
        validate_strategy_payload(payload)


def test_action_must_be_long_or_flat():
    payload = _valid_payload()
    payload["action"] = "sell_everything"

    with pytest.raises(ValidationError):
        validate_strategy_payload(payload)


def test_exit_rules_require_positive_values():
    payload = _valid_payload()
    payload["exits"][0]["value"] = -1

    with pytest.raises(ValidationError):
        validate_strategy_payload(payload)


def test_json_schema_exposes_required_fields():
    schema = StrategySchema.model_json_schema()

    for required_field in [
        "instrument",
        "sentiment_zscore",
        "lead_lag",
        "action",
        "atr_stop",
        "size_fraction",
        "exits",
    ]:
        assert required_field in schema.get("required", [])

    assert schema["properties"]["action"]["enum"] == ["long", "flat"]
