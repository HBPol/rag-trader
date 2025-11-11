"""Data pipelines for RAGTrader."""

from importlib.metadata import PackageNotFoundError, version

try:  # pragma: no cover - metadata may be missing in editable installs
    __version__ = version("ragtrader-pipelines")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

from importlib import import_module
from typing import TYPE_CHECKING, Any

_COINBASE_EXPORTS = {
    "CoinbaseClient",
    "CoinbaseOhlcvIngestion",
    "Granularity",
    "OhlcvRecord",
    "SqlAlchemyCandleRepository",
}

_CONTENT_EXPORTS = {
    "ArticleCandidate",
    "BaseContentAdapter",
    "ContentAggregator",
    "ContentIngestionJob",
    "CoinDeskAdapter",
    "CoinDeskContentSource",
    "CoinTelegraphAdapter",
    "CoinTelegraphContentSource",
    "KNOWN_TICKERS",
    "InMemoryDedupeCache",
    "NormalizedArticleRecord",
    "RedditContentSource",
    "RedditAdapter",
    "RedisDedupeCache",
    "SentimentRecord",
    "SqlAlchemyContentRepository",
    "UnsupportedLanguageError",
    "SourceFactoryError",
    "is_supported_ticker",
    "build_sources_from_env",
    "build_arg_parser",
    "default_content_sources",
    "main",
    "normalise_supported_ticker",
    "register_content_ingestion_job",
}

_SENTIMENT_EXPORTS = {
    "SentimentAspect",
    "SentimentClassifier",
    "SentimentLabel",
    "SentimentResult",
    "SentimentSeriesPoint",
    "SentimentZScore",
    "SentimentUnsupportedLanguageError",
    "ZScoreCalculator",
}

_ANALYTICS_EXPORTS = {
    "JoinStrategy",
    "rolling_pearson",
    "rolling_spearman",
}

if TYPE_CHECKING:  # pragma: no cover - import only for static analysis
    from .analytics import JoinStrategy, rolling_pearson, rolling_spearman  # noqa: F401
    from .coinbase import (  # noqa: F401
        CoinbaseClient,
        CoinbaseOhlcvIngestion,
        Granularity,
        OhlcvRecord,
        SqlAlchemyCandleRepository,
    )
    from .content import (  # noqa: F401
        KNOWN_TICKERS,
        ArticleCandidate,
        BaseContentAdapter,
        CoinDeskAdapter,
        CoinDeskContentSource,
        CoinTelegraphAdapter,
        CoinTelegraphContentSource,
        ContentAggregator,
        ContentIngestionJob,
        InMemoryDedupeCache,
        NormalizedArticleRecord,
        RedditAdapter,
        RedditContentSource,
        RedisDedupeCache,
        SentimentRecord,
        SourceFactoryError,
        SqlAlchemyContentRepository,
        UnsupportedLanguageError,
        build_arg_parser,
        build_sources_from_env,
        default_content_sources,
        is_supported_ticker,
        main,
        normalise_supported_ticker,
        register_content_ingestion_job,
    )
    from .sentiment import (  # noqa: F401
        SentimentAspect,
        SentimentClassifier,
        SentimentLabel,
        SentimentResult,
        SentimentSeriesPoint,
        SentimentUnsupportedLanguageError,
        SentimentZScore,
        ZScoreCalculator,
    )


def __getattr__(name: str) -> Any:
    if name in _COINBASE_EXPORTS:
        module = import_module(".coinbase", __name__)
        return getattr(module, name)
    if name in _CONTENT_EXPORTS:
        module = import_module(".content", __name__)
        return getattr(module, name)
    if name in _SENTIMENT_EXPORTS:
        module = import_module(".sentiment", __name__)
        return getattr(module, name)
    if name in _ANALYTICS_EXPORTS:
        module = import_module(".analytics", __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(
        list(globals().keys())
        + list(_COINBASE_EXPORTS)
        + list(_CONTENT_EXPORTS)
        + list(_SENTIMENT_EXPORTS)
        + list(_ANALYTICS_EXPORTS)
    )


__all__ = [
    "__version__",
    *_COINBASE_EXPORTS,
    *_CONTENT_EXPORTS,
    *_SENTIMENT_EXPORTS,
    *_ANALYTICS_EXPORTS,
]
