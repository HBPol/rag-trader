import json
import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.extend([str(REPO_ROOT / "api" / "src"), str(REPO_ROOT / "pipelines" / "src")])

from ragtrader_api.strategy.nl_to_dsl import (  # noqa: E402
    NaturalLanguageToDSLConverter,
    StrategyConversionError,
    UnsafeContentError,
)
from ragtrader_api.strategy.schema import StrategySchema  # noqa: E402


class FakeLLM:
    def __init__(self, response):
        self.response = response
        self.messages = None

    def complete(self, messages):
        self.messages = messages
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _strategy_payload():
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


def test_converter_requests_schema_and_parses_response():
    payload = _strategy_payload()
    llm = FakeLLM(json.dumps(payload))
    converter = NaturalLanguageToDSLConverter(llm)

    result = converter.convert("Go long when sentiment rises")

    assert isinstance(result, StrategySchema)
    assert result.instrument == payload["instrument"]
    assert llm.messages[0]["role"] == "system"
    assert "instrument" in llm.messages[0]["content"]
    assert "sentiment_zscore" in llm.messages[0]["content"]
    assert "Go long when sentiment rises" in llm.messages[1]["content"]


def test_converter_rejects_malformed_json():
    llm = FakeLLM("not valid json")
    converter = NaturalLanguageToDSLConverter(llm)

    with pytest.raises(StrategyConversionError):
        converter.convert("bad json please")


def test_converter_rejects_unsafe_content():
    llm = FakeLLM(UnsafeContentError("unsafe"))
    converter = NaturalLanguageToDSLConverter(llm)

    with pytest.raises(UnsafeContentError):
        converter.convert("something dangerous")
