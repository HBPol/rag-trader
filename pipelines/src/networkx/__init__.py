"""Compatibility shim for the ``networkx`` package used in analytics tests."""

from __future__ import annotations

import sys
from importlib import util
from importlib.machinery import PathFinder
from pathlib import Path
from types import ModuleType

module_dir = Path(__file__).resolve().parents[1]
search_path = [
    candidate
    for candidate in sys.path
    if Path(candidate).resolve() != module_dir.resolve()
]

spec = PathFinder.find_spec("networkx", search_path)
loaded: ModuleType | None = None
module: ModuleType | None = None
if spec is not None and spec.loader is not None and spec.origin != __file__:
    try:
        loaded = util.module_from_spec(spec)
        spec.loader.exec_module(loaded)
    except (ImportError, ModuleNotFoundError):
        loaded = None
    else:
        module = loaded

if module is None:  # pragma: no cover - executed when real dependency is unavailable
    from ragtrader_pipelines._compat.networkx import DiGraph as _DiGraph

    module = ModuleType("networkx")
    module.DiGraph = _DiGraph  # type: ignore[attr-defined]

globals().update(module.__dict__)
__all__ = getattr(
    module,
    "__all__",
    [name for name in globals() if not name.startswith("_")],
)


for name in (
    "util",
    "PathFinder",
    "Path",
    "ModuleType",
    "module",
    "search_path",
    "module_dir",
    "spec",
    "loaded",
):
    if name in globals():
        del globals()[name]
