"""Public alias of the shared specialist-proposal implementation."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module("puzzleops.proposals")
