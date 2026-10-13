import pytest
from puzzleops.native_z3 import native_version

@pytest.mark.skipif(native_version() is None,reason='Cross-family integration demonstration requires Z3')
def test_cross_family_demonstration():
    from examples.structured_demo import demonstrate
    r=demonstrate()['examples']
    assert r['word_arithmetic']['assignment']==dict(S=9,E=5,N=6,D=7,M=1,O=0,R=8,Y=2)
    assert r['temporal_events']['assignment']=={'red':0,'blue':3,'green':8}
    assert len(r['spatial_placement']['z3']['solutions'])==10
    assert r['contradiction']['status']=='UNSAT'
    assert r['ambiguous_glyph']['distinguishing_observations'][0]['observation_acquired'] is False
