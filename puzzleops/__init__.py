"""puzzleops is a deprecated alias for polya; import polya instead.

``import puzzleops.X`` returns the ``polya.X`` module object itself.
"""
import sys
from importlib import import_module
from importlib.machinery import ModuleSpec

from polya import __version__, find, run


class _AliasLoader:
    def __init__(self, module):
        self.module = module
        self.spec = module.__spec__

    def create_module(self, spec):
        return self.module

    def exec_module(self, module):
        # The import system overwrites __spec__ with the alias spec; keep polya's own.
        module.__spec__ = self.spec


class _AliasFinder:
    @staticmethod
    def find_spec(fullname, path=None, target=None):
        if not fullname.startswith("puzzleops."):
            return None
        module = import_module("polya" + fullname[len("puzzleops"):])
        return ModuleSpec(fullname, _AliasLoader(module))


# Run before PathFinder: an aliased package's __path__ points into polya, and
# ordinary discovery would otherwise load nested files a second time.
sys.meta_path.insert(0, _AliasFinder())
