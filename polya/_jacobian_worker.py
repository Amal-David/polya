"""Compatibility alias for the shared implementation."""
import sys
from puzzleops import _jacobian_worker as _implementation

sys.modules[__name__] = _implementation
