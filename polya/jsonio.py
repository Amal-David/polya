"""Public alias for the shared jsonio implementation."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module("puzzleops.jsonio")
