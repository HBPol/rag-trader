"""Convert natural language instructions into strategy DSL payloads."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from pydantic import ValidationError

from .schema import StrategySchema


class StrategyConversionError(RuntimeError):
    """Raised when an LLM response cannot be converted into the DSL."""


class UnsafeContentError(RuntimeError):
    """Raised when the LLM flags the request or response as unsafe."""


class ChatModel(Protocol):
    """Minimal protocol for chat-based LLM clients."""

    def complete(
        self, messages: Sequence[dict[str, str]]
    ) -> str:  # pragma: no cover - protocol
        """Generate a completion from a list of chat messages."""


@dataclass
class NaturalLanguageToDSLConverter:
    """Service that turns natural language prompts into validated strategies."""

    llm: ChatModel

    def _build_messages(self, instructions: str) -> list[dict[str, str]]:
        schema_json = json.dumps(StrategySchema.model_json_schema(), indent=2)
        system_prompt = (
            "You are a trading-strategy translation service. "
            "Convert natural language requests into a JSON object that strictly follows the provided schema. "
            "Do not include any text outside of the JSON response. "
            "Reject instructions that involve unsafe, malicious, or unrelated content.\n"
            "Strategy DSL JSON schema:\n"
            f"{schema_json}"
        )
        user_prompt = (
            "User request:\n"
            f"{instructions}\n"
            "Produce a single JSON object that validates against the schema above. "
            "Populate all required fields with concrete numeric values and emit only JSON."
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def convert(self, instructions: str) -> StrategySchema:
        """Convert natural language into a validated ``StrategySchema`` instance."""

        messages = self._build_messages(instructions)
        try:
            completion = self.llm.complete(messages)
        except UnsafeContentError:
            raise
        except Exception as exc:  # pragma: no cover - defensive fallback
            raise StrategyConversionError("LLM request failed") from exc

        try:
            payload = json.loads(completion)
        except json.JSONDecodeError as exc:
            raise StrategyConversionError("LLM response was not valid JSON") from exc

        try:
            return StrategySchema.validate_payload(payload)
        except ValidationError as exc:
            raise StrategyConversionError(
                "LLM response did not conform to the strategy DSL schema"
            ) from exc


__all__ = [
    "ChatModel",
    "NaturalLanguageToDSLConverter",
    "StrategyConversionError",
    "UnsafeContentError",
]
