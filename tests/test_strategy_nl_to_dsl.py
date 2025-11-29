import json
import pathlib
import sys

import pytest
from pydantic import ValidationError

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.extend([str(REPO_ROOT / "api" / "src"), str(REPO_ROOT / "pipelines" / "src")])

from ragtrader_api.strategy.nl_to_dsl import (  # noqa: E402
    NaturalLanguageToDSLConverter,
    StrategyConversionError,
    UnsafeContentError,
)
from ragtrader_api.strategy.schema import (  # noqa: E402
    StrategySchema,
    validate_strategy_payload,
)


class FakeChatModel:
    def __init__(self, response):
        self.response = response

    def complete(self, messages):
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _valid_payload() -> dict[str, object]:
    return {
        "instrument": "AAPL",
        "sentiment_zscore": 1.1,
        "lead_lag": 5,
        "action": "long",
        "atr_stop": 2.5,
        "size_fraction": 0.3,
        "exits": [
            {"kind": "take_profit", "value": 1.5},
            {"kind": "stop_loss", "value": 0.75},
        ],
    }


def test_convert_returns_valid_strategy_schema_from_json():
    llm = FakeChatModel(json.dumps(_valid_payload()))
    converter = NaturalLanguageToDSLConverter(llm)

    result = converter.convert("Please produce a valid strategy")

    assert isinstance(result, StrategySchema)
    assert result.instrument == "AAPL"
    assert result.exits[0].kind == "take_profit"


def test_convert_rejects_malformed_json():
    llm = FakeChatModel("{" * 3)
    converter = NaturalLanguageToDSLConverter(llm)

    with pytest.raises(StrategyConversionError):
        converter.convert("This should fail JSON parsing")


def test_convert_bubbles_unsafe_content_error():
    llm = FakeChatModel(UnsafeContentError("unsafe"))
    converter = NaturalLanguageToDSLConverter(llm)

    with pytest.raises(UnsafeContentError):
        converter.convert("something dangerous")


def test_convert_wraps_schema_validation_error():
    invalid_payload = _valid_payload()
    invalid_payload.pop("instrument")
    llm = FakeChatModel(json.dumps(invalid_payload))
    converter = NaturalLanguageToDSLConverter(llm)

    with pytest.raises(StrategyConversionError):
        converter.convert("missing instrument should fail validation")


def test_validate_payload_accepts_valid_input():
    payload = _valid_payload()

    result = StrategySchema.validate_payload(payload)

    assert result.instrument == payload["instrument"]
    assert result.size_fraction == pytest.approx(0.3)


def test_validate_payload_and_helper_reject_invalid_input():
    payload = _valid_payload()
    payload["action"] = "short"

    with pytest.raises(StrategyConversionError):
        NaturalLanguageToDSLConverter(FakeChatModel(json.dumps(payload))).convert(
            "invalid action triggers validation"
        )

    with pytest.raises(ValidationError):
        validate_strategy_payload(payload)
