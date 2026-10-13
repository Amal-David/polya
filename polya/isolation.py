"""Public alias for the shared isolation implementation."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module("puzzleops.isolation")
