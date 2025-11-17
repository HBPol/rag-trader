"""Smoke tests for planned analytics dependencies.

The analytics stack relies on a handful of scientific computing
libraries. Importing them directly helps us fail fast when they are
missing from a local environment or CI runner.
"""

from importlib import import_module

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "numpy",
        "scipy",
        "statsmodels",
        "networkx",
    ],
)
def test_can_import_analytics_dependency(module_name: str) -> None:
    """Ensure the analytics dependency is available to the runtime."""

    import_module(module_name)
