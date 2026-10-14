"""Shared whole-output equality-pattern checks."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module('puzzleops.equality_patterns')
