"""Public alias for the shared mechanisms implementation."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module("puzzleops.mechanisms")
