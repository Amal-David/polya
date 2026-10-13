"""Public alias for the shared session implementation."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module("puzzleops.session")
