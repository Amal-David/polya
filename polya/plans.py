"""Public alias for the shared typed-plan implementation."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module('puzzleops.plans')
