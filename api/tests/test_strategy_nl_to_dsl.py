import json

import pytest

from ragtrader_api.strategy.nl_to_dsl import (
    NaturalLanguageToDSLConverter,
    StrategyConversionError,
    UnsafeContentError,
)
from ragtrader_api.strategy.schema import StrategySchema


def _valid_payload() -> dict[str, object]:
    return {
        "instrument": "SPY",
        "sentiment_zscore": 0.1,
        "lead_lag": 0,
        "action": "long",
        "atr_stop": 1.0,
        "size_fraction": 0.5,
        "exits": [{"kind": "take_profit", "value": 1.0}],
    }


class CapturingChatModel:
    def __init__(self, response: str | Exception):
        self.response = response
        self.messages: list[dict[str, str]] | None = None

    def complete(self, messages: list[dict[str, str]]):
        self.messages = messages
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _assert_messages(
    converter: NaturalLanguageToDSLConverter,
    llm: CapturingChatModel,
    instructions: str,
) -> None:
    assert llm.messages is not None
    assert llm.messages == converter._build_messages(instructions)
    assert llm.messages[0]["role"] == "system"
    assert "Strategy DSL JSON schema" in llm.messages[0]["content"]
    assert (
        json.dumps(StrategySchema.model_json_schema(), indent=2)
        in llm.messages[0]["content"]
    )
    assert llm.messages[1]["role"] == "user"
    assert instructions in llm.messages[1]["content"]


def test_build_messages_includes_schema_and_user_prompt():
    instructions = "Trade SPY using sentiment"
    converter = NaturalLanguageToDSLConverter(CapturingChatModel("{}"))

    messages = converter._build_messages(instructions)

    assert messages[0]["role"] == "system"
    assert "Strategy DSL JSON schema" in messages[0]["content"]
    assert (
        json.dumps(StrategySchema.model_json_schema(), indent=2)
        in messages[0]["content"]
    )
    assert messages[1]["role"] == "user"
    assert instructions in messages[1]["content"]


def test_convert_returns_valid_strategy_schema_and_builds_messages():
    instructions = "Please produce a valid strategy"
    llm = CapturingChatModel(json.dumps(_valid_payload()))
    converter = NaturalLanguageToDSLConverter(llm)

    result = converter.convert(instructions)

    assert isinstance(result, StrategySchema)
    assert result.instrument == "SPY"
    assert result.exits[0].kind == "take_profit"
    _assert_messages(converter, llm, instructions)


def test_convert_rejects_malformed_json_and_builds_messages():
    instructions = "This should fail JSON parsing"
    llm = CapturingChatModel("{" * 3)
    converter = NaturalLanguageToDSLConverter(llm)

    with pytest.raises(StrategyConversionError):
        converter.convert(instructions)

    _assert_messages(converter, llm, instructions)


def test_convert_wraps_schema_validation_error_and_builds_messages():
    instructions = "missing instrument should fail validation"
    invalid_payload = _valid_payload()
    invalid_payload.pop("instrument")
    llm = CapturingChatModel(json.dumps(invalid_payload))
    converter = NaturalLanguageToDSLConverter(llm)

    with pytest.raises(StrategyConversionError):
        converter.convert(instructions)

    _assert_messages(converter, llm, instructions)


def test_convert_bubbles_unsafe_content_error_and_builds_messages():
    instructions = "something dangerous"
    llm = CapturingChatModel(UnsafeContentError("unsafe"))
    converter = NaturalLanguageToDSLConverter(llm)

    with pytest.raises(UnsafeContentError):
        converter.convert(instructions)

    _assert_messages(converter, llm, instructions)
