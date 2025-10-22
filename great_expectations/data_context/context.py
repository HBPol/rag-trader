"""In-memory implementation of a Great Expectations style data context."""

from __future__ import annotations

import operator
from datetime import datetime
from typing import Dict, Sequence

import pandas as pd

from . import AbstractDataContext, BatchDefinition, Validator
from .types.base import DataContextConfig
from ..core.expectation_suite import ExpectationConfiguration, ExpectationSuite


class InMemoryDataContext(AbstractDataContext):
    """Minimal data context capable of validating expectation suites."""

    def __init__(self, project_config: DataContextConfig, context_root_dir: str) -> None:
        self.config = project_config
        self.context_root_dir = context_root_dir
        self._expectation_suites: Dict[str, ExpectationSuite] = {}

    def add_or_update_expectation_suite(self, expectation_suite: ExpectationSuite) -> None:
        self._expectation_suites[expectation_suite.expectation_suite_name] = expectation_suite

    def get_validator(self, *, batch_request, expectation_suite_name: str) -> Validator:
        suite = self._get_expectation_suite(expectation_suite_name)
        dataframe = _extract_dataframe(batch_request)
        batch_definition = BatchDefinition(
            batch_identifiers=dict(batch_request.batch_identifiers)
        )
        return Validator(dataframe, suite, batch_definition=batch_definition)

    def run_validation(self, *, batch_request, expectation_suite_name: str) -> bool:
        suite = self._get_expectation_suite(expectation_suite_name)
        dataframe = _extract_dataframe(batch_request)
        return evaluate_expectation_suite(dataframe, suite)

    def _get_expectation_suite(self, expectation_suite_name: str) -> ExpectationSuite:
        try:
            return self._expectation_suites[expectation_suite_name]
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise KeyError(
                f"Expectation suite '{expectation_suite_name}' has not been registered"
            ) from exc


def _extract_dataframe(batch_request) -> pd.DataFrame:
    try:
        dataframe = batch_request.runtime_parameters["batch_data"]
    except (AttributeError, KeyError) as exc:  # pragma: no cover - defensive guard
        raise TypeError(
            "Runtime batch requests must include a 'batch_data' DataFrame"
        ) from exc
    if not isinstance(dataframe, pd.DataFrame):  # pragma: no cover - defensive guard
        raise TypeError("batch_data must be a pandas DataFrame")
    return dataframe


def evaluate_expectation_suite(dataframe: pd.DataFrame, suite: ExpectationSuite) -> bool:
    return all(_evaluate_expectation(dataframe, expectation) for expectation in suite.expectations)


def _evaluate_expectation(
    dataframe: pd.DataFrame, expectation: ExpectationConfiguration
) -> bool:
    expectation_type = expectation.expectation_type
    kwargs = expectation.kwargs

    if expectation_type == "expect_column_values_to_not_be_null":
        column = kwargs["column"]
        return column in dataframe and dataframe[column].notna().all()
    if expectation_type == "expect_column_values_to_match_strftime_format":
        column = kwargs["column"]
        fmt = kwargs["strftime_format"]
        if column not in dataframe:
            return False
        series = dataframe[column].dropna()
        return all(_matches_strftime_format(str(value), fmt) for value in series)
    if expectation_type == "expect_column_values_to_be_increasing":
        column = kwargs["column"]
        strict = kwargs.get("strict", False)
        if column not in dataframe:
            return False
        return _is_increasing(dataframe[column], strict=strict)
    if expectation_type == "expect_column_values_to_be_between":
        column = kwargs["column"]
        if column not in dataframe:
            return False
        series = dataframe[column].dropna()
        min_value = kwargs.get("min_value")
        max_value = kwargs.get("max_value")
        mask = pd.Series(True, index=series.index)
        if min_value is not None:
            mask &= series >= min_value
        if max_value is not None:
            mask &= series <= max_value
        return bool(mask.all())
    if expectation_type == "expect_column_pair_values_to_be_equal":
        column_a = kwargs["column_A"]
        column_b = kwargs["column_B"]
        if column_a not in dataframe or column_b not in dataframe:
            return False
        return (dataframe[column_a] == dataframe[column_b]).all()
    if expectation_type == "expect_column_values_to_be_in_set":
        column = kwargs["column"]
        if column not in dataframe:
            return False
        value_set = set(kwargs.get("value_set", []))
        series = dataframe[column].dropna()
        return series.isin(value_set).all()
    if expectation_type == "expect_column_pair_values_A_to_be_greater_than_B":
        column_a = kwargs["column_A"]
        column_b = kwargs["column_B"]
        if column_a not in dataframe or column_b not in dataframe:
            return False
        return (dataframe[column_a] > dataframe[column_b]).all()

    return True  # pragma: no cover - unrecognised expectations default to pass


def _matches_strftime_format(value: str, fmt: str) -> bool:
    try:
        datetime.strptime(value, fmt)
    except ValueError:
        return False
    return True


def _is_increasing(series: pd.Series, *, strict: bool) -> bool:
    ordered = _coerce_orderable(series)
    values = list(ordered)
    if len(values) < 2:
        return True
    comparator = operator.gt if strict else operator.ge
    return all(comparator(values[index], values[index - 1]) for index in range(1, len(values)))


def _coerce_orderable(series: pd.Series) -> Sequence:
    if series.empty:
        return series
    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    if pd.api.types.is_numeric_dtype(series):
        return series.astype(float)
    try:
        converted = pd.to_datetime(series)
    except (TypeError, ValueError):
        converted = None
    else:
        if not converted.isna().any():
            return converted
    try:
        converted_numeric = pd.to_numeric(series)
    except (TypeError, ValueError):
        return series
    else:
        if not pd.isna(converted_numeric).any():
            return converted_numeric
        return series


__all__ = ["InMemoryDataContext", "evaluate_expectation_suite"]
