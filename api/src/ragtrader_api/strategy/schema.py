"""Schema definitions for the strategy DSL used by the API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ExitRule(BaseModel):
    """Represents an exit condition for a strategy position."""

    kind: Literal["take_profit", "stop_loss", "time"]
    value: float = Field(..., gt=0, description="Threshold for the exit condition")

    model_config = ConfigDict(extra="forbid")


class StrategySchema(BaseModel):
    """Configuration schema for a sentiment-driven trading strategy."""

    instrument: str = Field(..., min_length=1, description="Instrument to trade")
    sentiment_zscore: float = Field(
        ..., description="Z-score threshold from sentiment model"
    )
    lead_lag: int = Field(..., ge=0, description="Lead/lag window for signal alignment")
    action: Literal["long", "flat"]
    atr_stop: float = Field(
        ..., gt=0, description="ATR multiple used for stop placement"
    )
    size_fraction: float = Field(
        ..., gt=0, le=1, description="Fraction of capital to allocate"
    )
    exits: list[ExitRule]

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def validate_payload(cls, payload: Mapping[str, object]) -> StrategySchema:
        """Validate raw payload data against the schema."""

        return cls.model_validate(payload)


def validate_strategy_payload(payload: Mapping[str, object]) -> StrategySchema:
    """Validate a raw JSON/YAML payload for strategy creation.

    Args:
        payload: Raw payload to validate.

    Returns:
        StrategySchema: Parsed strategy configuration.

    Raises:
        ValidationError: If the payload does not conform to the DSL schema.
    """

    try:
        return StrategySchema.validate_payload(payload)
    except ValidationError:
        # Re-raise so callers only need to import this helper
        raise


__all__ = ["ExitRule", "StrategySchema", "validate_strategy_payload"]
