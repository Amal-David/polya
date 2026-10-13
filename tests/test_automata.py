import itertools
import random
import pytest
from puzzleops.automata import Machine,from_runs,simulate,distinguish
from puzzleops.symbolic import solve


def groups(word): return [len(list(g)) for a,g in itertools.groupby(word) if a==1]

@pytest.mark.parametrize('runs',[[],[1],[2],[3],[1,1],[2,1],[1,2],[2,2],[1,1,1]])
def test_run_dfa_matches_independent_grouping(runs):
    m=Machine.model_validate(from_runs(runs)['machine'])
    for length in range(8):
        for word in itertools.product([0,1],repeat=length):
            assert simulate(m,list(word))['accepted']==(groups(word)==runs)


def toggler(inverted=False):
    return {'kind':'mealy','states':['a','b'],'initial':'a','alphabet':['tap','read'],
            'transitions':[{'source':s,'symbol':a,'target':('b' if s=='a' else 'a') if a=='tap' else s,
                            'output':str((s=='b') != inverted)} for s in ['a','b'] for a in ['tap','read']]}

def test_witness_is_shortest_and_replayed():
    a=toggler(); b=toggler(); b['transitions'][3]['output']='different'
    r=distinguish(a,b)
    assert r['status']=='DISTINGUISHED' and len(r['word'])==2
    assert r['left_replay']['outputs']!=r['right_replay']['outputs'] and r['shortest']
    for x in a['alphabet']: assert simulate(a,[x])['outputs']==simulate(b,[x])['outputs']

def test_complete_product_equivalence_and_budget_unknown():
    a=toggler()
    assert distinguish(a,a)['status']=='EQUIVALENT'
    assert distinguish(a,a,max_depth=0)['status']=='UNKNOWN'
    assert distinguish(a,a,max_pairs=1)['status']=='UNKNOWN'

def test_dfa_empty_witness_and_partial_sink():
    a=from_runs([])['machine'];b=from_runs([1])['machine']
    assert distinguish(a,b)['word']==[]
    assert simulate(b,[1,1,0])['accepted'] is False
    assert simulate(b,[1,1,0])['final_state'] is None

@pytest.mark.parametrize('mutation',['nondeterministic','missing_edge','unknown_state','wrong_kind_output'])
def test_machine_validation(mutation):
    a=toggler()
    if mutation=='nondeterministic': a['transitions'].append(a['transitions'][0])
    if mutation=='missing_edge': a['transitions'].pop()
    if mutation=='unknown_state': a['transitions'][0]['target']='nope'
    if mutation=='wrong_kind_output': a['kind']='dfa'
    with pytest.raises(ValueError): Machine.model_validate(a)

@pytest.mark.parametrize('seed',range(40))
def test_random_mealy_distinguishing_matches_independent_enumeration(seed):
    rng=random.Random(seed)
    def new():
        states=['a','b','c']
        return {'kind':'mealy','states':states,'initial':'a','alphabet':[0,1],
                'transitions':[{'source':s,'symbol':a,'target':rng.choice(states),'output':str(rng.randrange(2))} for s in states for a in [0,1]]}
    a,b=new(),new();r=distinguish(a,b)
    # Independent direct replay avoids Machine and simulate implementation.
    def direct(m,word):
        state=m['initial'];out=[]
        for symbol in word:
            t=next(t for t in m['transitions'] if t['source']==state and t['symbol']==symbol)
            state=t['target'];out.append(t['output'])
        return out
    bound=len(r['word']) if r['word'] is not None else 9
    found=None
    for n in range(1,bound+1):
        for word in itertools.product([0,1],repeat=n):
            if direct(a,word)!=direct(b,word): found=list(word);break
        if found is not None: break
    if found is None: assert r['status']=='EQUIVALENT'
    else: assert r['status']=='DISTINGUISHED' and len(found)==len(r['word'])


@pytest.mark.skipif(__import__('puzzleops.native_z3',fromlist=['native_version']).native_version() is None,reason='5x5 integration case requires Z3')
def test_nonogram_pattern_via_symbolic_dfa_constraints():
    variables={f'x{i}{j}':{'lower':0,'upper':1} for i in range(5) for j in range(5)}
    constraints=[];runs=[1,3,5,3,1]
    for i in range(5):
        for axis in ('row','column'):
            names=[f'x{i}{j}' if axis=='row' else f'x{j}{i}' for j in range(5)]
            constraints.append({'id':f'{axis}{i}','expr':{'op':'automaton','vars':names,'machine':from_runs([runs[i]])['machine']}})
    r=solve({'variables':variables,'constraints':constraints},backend='auto',max_solutions=2)
    assert r['complete'] and len(r['solutions'])==1
    a=r['solutions'][0]
    assert [[a[f'x{i}{j}'] for j in range(5)] for i in range(5)]==[
        [0,0,1,0,0],[0,1,1,1,0],[1,1,1,1,1],[0,1,1,1,0],[0,0,1,0,0]]
