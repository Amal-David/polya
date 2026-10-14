"""Public alias for the shared crypto-target implementation."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module('puzzleops.crypto_targets')
