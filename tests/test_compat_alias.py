import polya
import puzzleops


def test_puzzleops_alias_reexports_polya_api():
    assert puzzleops.run is polya.run
    assert puzzleops.find is polya.find
