import itertools
import random
import pytest
from polya.learning import learn_local,learn_mealy
from polya.automata import distinguish,simulate


def machine(seed=0):
    rng=random.Random(seed); states=[f'q{i}' for i in range(rng.randrange(2,5))]
    return {'kind':'mealy','states':states,'alphabet':['a','b'],'initial':states[0],
            'transitions':[{'source':s,'symbol':a,'target':rng.choice(states),'output':str(rng.randrange(2))}
                           for s in states for a in ['a','b']]}

@pytest.mark.parametrize('seed',range(30))
def test_learn_random_local_machines_and_cross_check_exactly(seed):
    target=machine(seed);r=learn_local(target,max_depth=6,max_equivalence_tests=5000)
    assert r['status']=='BOUNDED_CONFORMANCE'
    assert r['global_equivalence_proven'] is False
    assert r['stats']['physical_steps']<=100000
    assert distinguish(target,r['machine'])['status']=='EQUIVALENT'


def test_bound_is_not_global_equivalence():
    # A rare response appears only after six a's, outside the chosen test depth.
    states=[f'q{i}' for i in range(7)]
    target={'kind':'mealy','states':states,'alphabet':['a'],'initial':'q0','transitions':[
        {'source':s,'symbol':'a','target':states[min(i+1,6)],'output':'special' if i==5 else 'ordinary'} for i,s in enumerate(states)]}
    r=learn_local(target,max_depth=3)
    assert r['status']=='BOUNDED_CONFORMANCE' and not r['global_equivalence_proven']
    cross=distinguish(target,r['machine'])
    assert cross['status']=='DISTINGUISHED' and len(cross['word'])==6

@pytest.mark.parametrize('kw',[{'max_queries':1},{'max_steps':1},{'max_equivalence_tests':1},{'max_rounds':1,'max_states':1}])
def test_learning_budgets_are_explicit(kw):
    r=learn_local(machine(5),**kw)
    assert r['status']=='BUDGET_EXHAUSTED' and not r['complete'] and not r['global_equivalence_proven']


def test_nonrepeatable_reset_is_reported():
    class BadReset:
        def __init__(self): self.counter=0
        def reset(self): pass
        def step(self,a): self.counter+=1; return str(self.counter)
    r=learn_mealy(BadReset(),['a'])
    assert r['status']=='INCONSISTENT_OBSERVATIONS' and r['machine'] is None


def test_native_api_only_requires_reset_and_step():
    class Hidden:
        def reset(self): self.state=0
        def step(self,a):
            if a=='toggle': self.state=1-self.state
            return str(self.state)
    r=learn_mealy(Hidden(),['toggle','read'],max_depth=4)
    assert r['status']=='BOUNDED_CONFORMANCE'
    assert simulate(r['machine'],['toggle','read','toggle'])['outputs']==['1','1','0']


def test_aalpy_availability_is_honest():
    import importlib.util
    if importlib.util.find_spec('aalpy'): pytest.skip('AALpy installed; tested separately')
    r=learn_local(machine(),learner='aalpy')
    assert r['status']=='UNAVAILABLE' and r['stats']['physical_steps']==0
