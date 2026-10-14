"""These are integration tests, not mock-based substitutes for missing packages."""
import importlib.util
import json
import pytest
from polya.symbolic import solve,analyze
from polya.model import op
from polya.automata import from_runs,distinguish
from polya.learning import learn_local

HAS_CP=importlib.util.find_spec('ortools') is not None
HAS_AALPY=importlib.util.find_spec('aalpy') is not None

@pytest.mark.skipif(not HAS_CP,reason='OR-Tools unavailable: dependency download blocked in build environment')
def test_cpsat_globals_boolean_and_empty_edge_cases():
    for runs in ([],[1],[2],[1,1]):
        m={'variables':{f'x{i}':{'lower':0,'upper':1} for i in range(5)},
           'constraints':[{'id':'row','expr':{'op':'automaton','vars':[f'x{i}' for i in range(5)],'machine':from_runs(runs)['machine']}}]}
        cp=solve(m,backend='cpsat'); ref=solve(m,backend='reference')
        assert {json.dumps(x,sort_keys=True) for x in cp['solutions']}=={json.dumps(x,sort_keys=True) for x in ref['solutions']}
    m={'variables':{'x':{'lower':0,'upper':3},'y':{'lower':0,'upper':3},'b':{'kind':'bool'}},
       'constraints':[{'id':'a','expr':op('all_different','x','y')},
                      {'id':'b','expr':op('eq','b',op('lt','x','y'))},
                      {'id':'c','expr':op('eq',op('ite','b','x','y'),1)}]}
    assert len(solve(m,backend='cpsat')['solutions'])==len(solve(m,backend='reference')['solutions'])
    assert solve({'variables':{'x':{'values':[]}}},backend='cpsat')['status']=='UNSAT'
    assert solve({'variables':{}},backend='cpsat')['solutions']==[{}]
    m['answer_variables']=['x']; m['constraints']=[{'id':'x','expr':op('eq','x',2)}]
    assert analyze(m,backend='cpsat')['uniqueness']=='UNIQUE'

@pytest.mark.skipif(not HAS_AALPY,reason='AALpy unavailable: dependency download blocked in build environment')
def test_aalpy_end_to_end_and_exact_product_crosscheck():
    m={'kind':'mealy','states':['a','b'],'alphabet':[0,1],'initial':'a','transitions':[
        {'source':s,'symbol':a,'target':'b' if a==1 else 'a','output':s} for s in ['a','b'] for a in [0,1]]}
    r=learn_local(m,learner='aalpy',max_depth=5)
    assert r['status']=='BOUNDED_CONFORMANCE'
    assert distinguish(m,r['machine'])['status']=='EQUIVALENT'
    assert not r['global_equivalence_proven']
