"""YAML parsing utilities."""

from __future__ import annotations

import ast
from typing import Any, List, Mapping


def _parse_scalar(value: str) -> Any:
    if value == "":
        return ""
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    if value.startswith("[") and value.endswith("]"):
        return ast.literal_eval(value)
    if (value.startswith("\"") and value.endswith("\"")) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def _parse_meta(lines: List[str], start_index: int) -> tuple[Mapping[str, Any], int]:
    meta: dict[str, Any] = {}
    index = start_index
    while index < len(lines):
        line = lines[index]
        if not line.startswith("  "):
            break
        key, _, raw_value = line.strip().partition(":")
        meta[key] = _parse_scalar(raw_value.strip())
        index += 1
    return meta, index


def _parse_kwargs(lines: List[str], start_index: int) -> tuple[Mapping[str, Any], int]:
    kwargs: dict[str, Any] = {}
    index = start_index
    while index < len(lines):
        line = lines[index]
        if not line.startswith("      "):
            break
        key, _, raw_value = line.strip().partition(":")
        kwargs[key] = _parse_scalar(raw_value.strip())
        index += 1
    return kwargs, index


def _parse_expectation(lines: List[str], start_index: int) -> tuple[Mapping[str, Any], int]:
    expectation: dict[str, Any] = {}
    index = start_index
    line = lines[index]
    prefix = line[3:].strip()
    if prefix:
        key, _, raw_value = prefix.partition(":")
        expectation[key.strip()] = _parse_scalar(raw_value.strip())
    index += 1
    while index < len(lines):
        line = lines[index]
        if not line.startswith("    "):
            break
        stripped = line.strip()
        if stripped.endswith(":"):
            key = stripped[:-1]
            if key == "kwargs":
                kwargs, index = _parse_kwargs(lines, index + 1)
                expectation[key] = kwargs
            else:
                nested, index = _parse_meta(lines, index + 1)
                expectation[key] = nested
        else:
            key, _, raw_value = stripped.partition(":")
            expectation[key] = _parse_scalar(raw_value.strip())
            index += 1
    return expectation, index


def _fallback_parse(yaml_str: str) -> Mapping[str, Any]:
    lines = [line.rstrip() for line in yaml_str.splitlines() if line.strip()]
    index = 0
    document: dict[str, Any] = {}
    while index < len(lines):
        line = lines[index]
        if line.startswith("meta:"):
            meta, index = _parse_meta(lines, index + 1)
            document["meta"] = meta
            continue
        if line.startswith("expectation_suite_name:"):
            _, _, raw_value = line.partition(":")
            document["expectation_suite_name"] = _parse_scalar(raw_value.strip())
            index += 1
            continue
        if line.startswith("expectations:"):
            expectations: list[Mapping[str, Any]] = []
            index += 1
            while index < len(lines) and lines[index].startswith("  -"):
                expectation, index = _parse_expectation(lines, index)
                expectations.append(expectation)
            document["expectations"] = expectations
            continue
        index += 1
    return document


class YAMLHandler:
    """Parse YAML data using :mod:`yaml` when available, otherwise fallback."""

    def __init__(self) -> None:
        try:
            import yaml as _yaml  # type: ignore
        except ModuleNotFoundError:  # pragma: no cover - depends on environment
            self._yaml = None
        else:
            self._yaml = _yaml

    def load(self, yaml_str: str) -> Any:
        if self._yaml is not None:
            return self._yaml.safe_load(yaml_str)
        return _fallback_parse(yaml_str)


__all__ = ["YAMLHandler"]
