"""Feature-detected Python runtime support; never changes process-wide policy.

CPython 3.15 gets native immutable maps and sentinels. Older interpreters use
stdlib fallbacks. No GIL, JIT, lazy-import, or interpreter setting is enabled here.
"""
from __future__ import annotations

import builtins
from collections.abc import Mapping
import importlib.util
import platform
import sys
import sysconfig
from types import MappingProxyType
from typing import TypeVar

K = TypeVar("K")
V = TypeVar("V")
_NATIVE_FROZENDICT = getattr(builtins, "frozendict", None)
_NATIVE_SENTINEL = getattr(builtins, "sentinel", None)
UNSET = _NATIVE_SENTINEL("UNSET") if _NATIVE_SENTINEL is not None else object()


def freeze_mapping(values: Mapping[K, V]) -> Mapping[K, V]:
    """Own an immutable *shallow* snapshot; callers must freeze nested values."""
    copied = dict(values)
    return _NATIVE_FROZENDICT(copied) if _NATIVE_FROZENDICT is not None else MappingProxyType(copied)


def execution_mode() -> dict:
    """Cheap live observations: a dependency import may re-enable the GIL."""
    gil_probe = getattr(sys, "_is_gil_enabled", None)
    jit = getattr(sys, "_jit", None)
    return {
        "gil_enabled": bool(gil_probe()) if gil_probe else None,
        "jit_available": bool(jit.is_available()) if jit is not None else False,
        "jit_enabled": bool(jit.is_enabled()) if jit is not None else False,
        "utf8_mode": bool(sys.flags.utf8_mode),
    }


def inspect_runtime(*, probe_accelerators: bool = False) -> dict:
    """Report this interpreter's capabilities, not third-party certification."""
    from .hardware import inspect_hardware
    result = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "soabi": sysconfig.get_config_var("SOABI"),
        "free_threaded_build": sysconfig.get_config_var("Py_GIL_DISABLED") == 1,
        "native_frozendict": _NATIVE_FROZENDICT is not None,
        "native_sentinel": _NATIVE_SENTINEL is not None,
        "lazy_imports_supported": hasattr(sys, "get_lazy_imports"),
        "profiling_package": importlib.util.find_spec("profiling") is not None,
        "thread_policy": "Independent calls only; do not share mutable models, solver contexts, sessions or learners.",
        "hardware": inspect_hardware(probe_accelerators=probe_accelerators),
        "scope": "Observed runtime features. Availability is not a speedup or integration certificate.",
    }
    result.update(execution_mode())
    return result
