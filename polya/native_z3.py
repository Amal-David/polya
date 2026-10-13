"""Public alias for the shared native_z3 implementation."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module("puzzleops.native_z3")
