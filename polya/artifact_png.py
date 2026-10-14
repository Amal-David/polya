"""Public alias for the shared PNG extraction implementation."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module('puzzleops.artifact_png')
