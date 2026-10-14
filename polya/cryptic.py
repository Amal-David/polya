"""Public alias for the shared cryptic implementation."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module("puzzleops.cryptic")
