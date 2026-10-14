import pytest

import polya
import puzzleops


def test_puzzleops_alias_reexports_polya_api():
    assert puzzleops.run is polya.run
    assert puzzleops.find is polya.find


def test_puzzleops_submodules_are_the_polya_modules():
    import polya.catalog
    import polya.model
    import puzzleops.catalog
    import puzzleops.model
    from puzzleops.model import op
    assert puzzleops.model is polya.model
    assert op is polya.model.op
    assert puzzleops.catalog.REGISTRY is polya.catalog.REGISTRY
    assert polya.model.__spec__.name == "polya.model"
    with pytest.raises(ModuleNotFoundError):
        import puzzleops.does_not_exist  # noqa: F401
