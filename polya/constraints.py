"""Public alias for the shared constraints implementation."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module("puzzleops.constraints")
