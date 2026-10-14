import os
import random
import pytest
from polya.automata import distinguish
from polya.native_product import compare


def pair(seed):
    rng=random.Random(seed)
    def model():
        states=[f'q{i}' for i in range(rng.randrange(1,6))]
        return {'kind':'mealy','states':states,'alphabet':['a',0],'initial':states[0],
                'transitions':[{'source':s,'symbol':a,'target':rng.choice(states),'output':rng.choice(['x','y'])}
                               for s in states for a in ['a',0]]}
    a=model();return a,a if seed%3==0 else model()


@pytest.mark.parametrize('seed',range(35))
def test_dense_python_matches_original_dictionary_search(seed):
    left,right=pair(seed)
    for options in ({},{'max_pairs':1},{'max_depth':0},{'max_depth':1}):
        a=distinguish(left,right,**options);b=compare(left,right,**options)
        for key in ('status','word','expanded_pairs','discovered_pairs','complete','reason'):
            assert a[key]==b[key],(key,a,b)


@pytest.mark.skipif(not os.environ.get('POLYA_RUST_LIB'),reason='experimental Rust library not built')
@pytest.mark.parametrize('seed',range(35))
def test_real_rust_matches_original_and_dense_python(seed):
    left,right=pair(seed)
    for options in ({},{'max_pairs':1},{'max_depth':0},{'max_depth':2}):
        expected=compare(left,right,**options)
        actual=compare(left,right,backend='rust',library_path=os.environ['POLYA_RUST_LIB'],**options)
        for key in ('status','word','expanded_pairs','discovered_pairs','complete','reason'):
            assert actual[key]==expected[key]


def test_native_request_cannot_be_selected_through_operation_registry():
    from polya import run
    with pytest.raises(ValueError):run('native_product.compare',{'library_path':'untrusted'})
