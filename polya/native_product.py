"""Public alias for the shared native_product implementation."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module("puzzleops.native_product")
