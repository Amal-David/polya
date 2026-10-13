"""Public alias for the shared cpsat_backend implementation."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module("puzzleops.cpsat_backend")
