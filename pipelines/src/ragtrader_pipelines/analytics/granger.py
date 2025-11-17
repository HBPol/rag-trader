"""Granger causality helpers for analytics workflows."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Literal, Protocol, Self, cast, overload

pd: Any = import_module("pandas")

try:  # pragma: no cover - exercised when statsmodels is available
    from statsmodels.tsa.stattools import adfuller, grangercausalitytests
except ModuleNotFoundError:  # pragma: no cover - fallback for constrained environments
    from ._statsmodels_fallback import adfuller, grangercausalitytests


MAX_AUTOREGRESSIVE_ORDER = 12

Direction = Literal["leader_causes_follower", "follower_causes_leader"]


class SeriesLike(Protocol):
    """Subset of the pandas ``Series`` API required by this module."""

    name: str | None

    @property
    def empty(self) -> bool: ...

    def dropna(self) -> Self: ...

    def to_numpy(self, dtype: type[float]) -> Any: ...

    def rename(self, name: str) -> Self: ...


class DataFrameLike(Protocol):
    """Subset of the pandas ``DataFrame`` API required by this module."""

    @property
    def empty(self) -> bool: ...

    def dropna(self) -> Self: ...

    def astype(self, dtype: type[float]) -> Self: ...

    @overload
    def __getitem__(self, key: str) -> SeriesLike: ...

    @overload
    def __getitem__(self, key: list[str]) -> Self: ...

    def to_numpy(self, dtype: type[float]) -> Any: ...

    def __len__(self) -> int: ...


class GrangerCausalityError(RuntimeError):
    """Base error for Granger causality helpers."""


class InsufficientSamplesError(GrangerCausalityError):
    """Raised when a series does not contain enough observations."""


class NonStationarySeriesError(GrangerCausalityError):
    """Raised when a series fails the stationarity test."""


@dataclass(frozen=True, slots=True)
class StationarityTestResult:
    """Outcome of an Augmented Dickey-Fuller stationarity test."""

    name: str
    statistic: float
    p_value: float
    n_obs: int
    is_stationary: bool


@dataclass(frozen=True, slots=True)
class DirectionalGrangerResult:
    """Summary of the Granger test for a single causal direction."""

    direction: Direction
    best_lag: int
    p_value: float
    reject_null: bool


@dataclass(frozen=True, slots=True)
class GrangerCausalitySummary:
    """Aggregate summary of the Granger causality assessment."""

    max_lag: int
    significance: float
    leader_stationarity: StationarityTestResult
    follower_stationarity: StationarityTestResult
    leader_to_follower: DirectionalGrangerResult
    follower_to_leader: DirectionalGrangerResult

    def inferred_direction(
        self,
    ) -> Literal["leader", "follower", "bidirectional", "none"]:
        """Return the most plausible causal direction from the test results."""

        leader_causes = self.leader_to_follower.reject_null
        follower_causes = self.follower_to_leader.reject_null
        if leader_causes and follower_causes:
            return "bidirectional"
        if leader_causes:
            return "leader"
        if follower_causes:
            return "follower"
        return "none"


def test_stationarity(
    series: SeriesLike, *, name: str | None = None, significance: float = 0.05
) -> StationarityTestResult:
    """Run an Augmented Dickey-Fuller test and return its outcome."""

    if not 0 < significance < 1:
        raise ValueError("Significance level must be between 0 and 1")

    resolved_name = name or series.name or "series"
    cleaned = series.dropna()
    if cleaned.empty:
        raise InsufficientSamplesError(
            f"Series '{resolved_name}' has no observations after dropping NaNs"
        )

    values = cleaned.to_numpy(dtype=float)
    if values.size < 3:
        raise InsufficientSamplesError(
            "Series "
            f"'{resolved_name}' requires at least 3 observations "
            "for stationarity testing"
        )

    try:
        statistic, p_value, _, n_obs, *_ = adfuller(values, autolag="AIC")
    except ValueError as exc:  # pragma: no cover - defensive wrapping
        message = f"Stationarity test failed for series '{resolved_name}': {exc}"
        raise InsufficientSamplesError(message) from exc

    is_stationary = float(p_value) < significance
    return StationarityTestResult(
        name=resolved_name,
        statistic=float(statistic),
        p_value=float(p_value),
        n_obs=int(n_obs),
        is_stationary=is_stationary,
    )


def run_granger_causality(
    leader: SeriesLike,
    follower: SeriesLike,
    *,
    max_lag: int | None = None,
    significance: float = 0.05,
) -> GrangerCausalitySummary:
    """Run Granger causality tests for both leader→follower and follower→leader."""

    if not 0 < significance < 1:
        raise ValueError("Significance level must be between 0 and 1")

    aligned = _prepare_aligned_data(leader, follower)
    selected_max_lag = _select_max_lag(len(aligned), max_lag)

    leader_stationarity = test_stationarity(
        aligned["leader"], name="leader", significance=significance
    )
    if not leader_stationarity.is_stationary:
        raise NonStationarySeriesError(
            "Leader series is not stationary (ADF p-value="
            f"{leader_stationarity.p_value:.4f})"
        )

    follower_stationarity = test_stationarity(
        aligned["follower"], name="follower", significance=significance
    )
    if not follower_stationarity.is_stationary:
        raise NonStationarySeriesError(
            "Follower series is not stationary (ADF p-value="
            f"{follower_stationarity.p_value:.4f})"
        )

    leader_to_follower = _run_directional_test(
        aligned,
        cause="leader",
        effect="follower",
        direction="leader_causes_follower",
        max_lag=selected_max_lag,
        significance=significance,
    )
    follower_to_leader = _run_directional_test(
        aligned,
        cause="follower",
        effect="leader",
        direction="follower_causes_leader",
        max_lag=selected_max_lag,
        significance=significance,
    )

    return GrangerCausalitySummary(
        max_lag=selected_max_lag,
        significance=significance,
        leader_stationarity=leader_stationarity,
        follower_stationarity=follower_stationarity,
        leader_to_follower=leader_to_follower,
        follower_to_leader=follower_to_leader,
    )


def _prepare_aligned_data(leader: SeriesLike, follower: SeriesLike) -> DataFrameLike:
    """Align the leader and follower series and validate the sample size."""

    concatenated = pd.concat(
        [leader.rename("leader"), follower.rename("follower")], axis=1, join="inner"
    )
    aligned = cast(DataFrameLike, concatenated.dropna())

    if aligned.empty:
        raise InsufficientSamplesError(
            "Leader and follower series have no overlapping observations"
        )

    return aligned.astype(float)


def _select_max_lag(sample_size: int, requested: int | None) -> int:
    """Select a bounded autoregressive order for the Granger test."""

    if sample_size < 3:
        raise InsufficientSamplesError(
            "At least three aligned observations are required "
            "for Granger causality testing"
        )

    max_allowed = min(MAX_AUTOREGRESSIVE_ORDER, sample_size - 2)
    if max_allowed < 1:
        raise InsufficientSamplesError(
            "Unable to compute a valid lag order with the available observations"
        )

    if requested is None:
        return max_allowed

    if requested < 1:
        raise ValueError("Maximum lag must be a positive integer")
    if requested > max_allowed:
        raise InsufficientSamplesError(
            "Requested lag order "
            f"{requested} exceeds what the sample size {sample_size} supports"
        )
    return requested


def _run_directional_test(
    data: DataFrameLike,
    *,
    cause: str,
    effect: str,
    direction: Direction,
    max_lag: int,
    significance: float,
) -> DirectionalGrangerResult:
    """Execute the directional Granger test and summarise its outcome."""

    values = data[[effect, cause]].to_numpy(dtype=float)

    try:
        results = grangercausalitytests(values, maxlag=max_lag, verbose=False)
    except ValueError as exc:  # pragma: no cover - defensive wrapping
        message = (
            f"Granger causality computation failed for direction '{direction}': {exc}"
        )
        raise InsufficientSamplesError(message) from exc

    best_lag = min(results, key=lambda lag: float(results[lag][0]["ssr_ftest"][1]))
    best_p_value = float(results[best_lag][0]["ssr_ftest"][1])

    return DirectionalGrangerResult(
        direction=direction,
        best_lag=best_lag,
        p_value=best_p_value,
        reject_null=best_p_value < significance,
    )


__all__ = [
    "Direction",
    "DirectionalGrangerResult",
    "GrangerCausalityError",
    "GrangerCausalitySummary",
    "InsufficientSamplesError",
    "NonStationarySeriesError",
    "StationarityTestResult",
    "run_granger_causality",
    "test_stationarity",
]
