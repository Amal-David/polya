"""Public alias for the separately installed Jacobian mathematical bridge."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module("puzzleops.jacobian_bridge")
