"""Rule-based sentiment classification utilities."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum


class SentimentLabel(str, Enum):
    """High-level polarity labels emitted by the classifier."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class SentimentAspect(str, Enum):
    """Aspect tags describing why a snippet scored a given way."""

    HYPE = "hype"
    REGULATORY = "regulatory"
    SECURITY = "security"


class UnsupportedLanguageError(ValueError):
    """Raised when the classifier encounters non-English content."""


@dataclass(frozen=True)
class SentimentResult:
    """Container describing the classifier output."""

    label: SentimentLabel
    confidence: float
    aspects: Sequence[SentimentAspect]
    coins: Sequence[str]


class SentimentClassifier:
    """Very small rule-based classifier used for guardrail tests."""

    _POSITIVE_KEYWORDS = {
        "surge",
        "surges",
        "breakout",
        "breakouts",
        "bullish",
        "rally",
        "rallies",
        "record",
        "records",
        "optimism",
        "optimistic",
        "upgrade",
        "upgrades",
        "sustained",
        "inflow",
        "inflows",
        "greenlight",
        "climb",
        "climbs",
        "gain",
        "gains",
        "strength",
    }

    _NEGATIVE_KEYWORDS = {
        "slump",
        "slumps",
        "slumping",
        "selloff",
        "decline",
        "declines",
        "drop",
        "drops",
        "warning",
        "warn",
        "warns",
        "volatile",
        "volatility",
        "investigation",
        "investigators",
        "wells notice",
        "lawsuit",
        "crackdown",
        "risk",
        "risks",
        "unresolved",
        "disclosure",
    }

    _HYPE_KEYWORDS = {
        "to the moon",
        "moonshot",
        "hype",
        "breakout",
        "record",
        "surge",
        "rally",
    }

    _REGULATORY_KEYWORDS = {
        "sec",
        "regulator",
        "regulators",
        "regulatory",
        "compliance",
        "investigation",
        "lawsuit",
        "wells notice",
    }

    _SECURITY_KEYWORDS = {
        "hack",
        "hacked",
        "exploit",
        "breach",
        "vulnerability",
        "incident",
        "security",
        "disclosure",
    }

    _LANGUAGE_KEYS = ("language", "lang", "locale")
    _ALLOWED_REGION_TOKENS = {"us", "gb", "uk", "au", "ca", "nz", "sg", "in"}

    def classify(
        self, text: str, metadata: Mapping[str, object] | None
    ) -> SentimentResult:
        """Classify sentiment using simple keyword heuristics."""

        cleaned_text = (text or "").strip()
        if not cleaned_text:
            return SentimentResult(
                label=SentimentLabel.UNKNOWN,
                confidence=0.0,
                aspects=(),
                coins=(),
            )

        metadata = metadata or {}
        self._enforce_english(metadata)

        normalised_coins = self._normalise_coins(metadata.get("coins"))

        lowercase_text = cleaned_text.lower()
        pos_hits = self._count_matches(lowercase_text, self._POSITIVE_KEYWORDS)
        neg_hits = self._count_matches(lowercase_text, self._NEGATIVE_KEYWORDS)

        pos_hits += self._metadata_positive_boost(metadata)
        neg_hits += self._metadata_negative_boost(metadata)

        score = pos_hits - neg_hits
        if score > 0:
            label = SentimentLabel.BULLISH
            confidence = min(0.6 + 0.08 * pos_hits, 0.95)
        elif score < 0:
            label = SentimentLabel.BEARISH
            confidence = min(0.55 + 0.08 * neg_hits, 0.9)
        else:
            label = SentimentLabel.NEUTRAL
            confidence = min(0.4 + 0.05 * (pos_hits + neg_hits), 0.6)

        aspects = self._derive_aspects(lowercase_text, metadata)

        return SentimentResult(
            label=label,
            confidence=round(confidence, 3),
            aspects=tuple(sorted(aspects, key=lambda a: a.value)),
            coins=normalised_coins,
        )

    def _enforce_english(self, metadata: Mapping[str, object]) -> None:
        for key in self._LANGUAGE_KEYS:
            value = metadata.get(key)
            if value is None:
                continue
            languages = self._extract_languages(value)
            if not languages:
                continue
            english_tokens = {
                lang for lang in languages if lang in {"en", "eng", "english"}
            }
            residual = languages - english_tokens - self._ALLOWED_REGION_TOKENS
            if not english_tokens or residual:
                raise UnsupportedLanguageError(
                    "Sentiment classifier only supports English-language inputs."
                )

    def _extract_languages(self, value: object) -> set[str]:
        if isinstance(value, str):
            tokens = self._tokenise_language_string(value)
        elif isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
            tokens: set[str] = set()
            for item in value:
                if isinstance(item, str):
                    tokens.update(self._tokenise_language_string(item))
            return tokens
        else:
            return set()
        return tokens

    @staticmethod
    def _tokenise_language_string(value: str) -> set[str]:
        lowered = value.strip().lower()
        separators = {"-", "_", "/", ",", "|"}
        for sep in separators:
            lowered = lowered.replace(sep, " ")
        return {token for token in lowered.split() if token}

    @staticmethod
    def _normalise_coins(coins: object) -> tuple[str, ...]:
        if coins is None:
            return ()
        if isinstance(coins, str):
            iterable: Iterable[object] = [coins]
        elif isinstance(coins, Iterable) and not isinstance(coins, (bytes, bytearray)):
            iterable = coins
        else:
            return ()
        uppercased = {
            str(token).strip().upper() for token in iterable if str(token).strip()
        }
        return tuple(sorted(uppercased))

    @staticmethod
    def _count_matches(text: str, keywords: set[str]) -> int:
        return sum(1 for keyword in keywords if keyword in text)

    def _metadata_positive_boost(self, metadata: Mapping[str, object]) -> int:
        boost = 0
        hype = metadata.get("hype_signals")
        if isinstance(hype, Iterable) and not isinstance(hype, (str, bytes, bytearray)):
            boost += sum(1 for item in hype if str(item).strip())
        return boost

    def _metadata_negative_boost(self, metadata: Mapping[str, object]) -> int:
        boost = 0
        for key in ("regulatory_cues", "security_incidents"):
            value = metadata.get(key)
            if isinstance(value, Iterable) and not isinstance(
                value, (str, bytes, bytearray)
            ):
                boost += sum(1 for item in value if str(item).strip())
        return boost

    def _derive_aspects(
        self, text: str, metadata: Mapping[str, object]
    ) -> set[SentimentAspect]:
        aspects: set[SentimentAspect] = set()
        hype_values = metadata.get("hype_signals")
        if self._has_values(hype_values) or self._has_keyword(
            text, self._HYPE_KEYWORDS
        ):
            aspects.add(SentimentAspect.HYPE)

        if self._has_values(metadata.get("regulatory_cues")) or self._has_keyword(
            text, self._REGULATORY_KEYWORDS
        ):
            aspects.add(SentimentAspect.REGULATORY)

        if self._has_values(metadata.get("security_incidents")) or self._has_keyword(
            text, self._SECURITY_KEYWORDS
        ):
            aspects.add(SentimentAspect.SECURITY)

        return aspects

    @staticmethod
    def _has_values(container: object) -> bool:
        if isinstance(container, Iterable) and not isinstance(
            container, (str, bytes, bytearray)
        ):
            return any(str(item).strip() for item in container)
        return False

    @staticmethod
    def _has_keyword(text: str, keywords: set[str]) -> bool:
        return any(keyword in text for keyword in keywords)


SentimentUnsupportedLanguageError = UnsupportedLanguageError


__all__ = [
    "SentimentLabel",
    "SentimentAspect",
    "UnsupportedLanguageError",
    "SentimentUnsupportedLanguageError",
    "SentimentResult",
    "SentimentClassifier",
]
