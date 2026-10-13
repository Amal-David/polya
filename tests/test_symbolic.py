import copy
import itertools
import json
import random
from unittest import mock
import pytest

from puzzleops import run,find
from puzzleops.model import PuzzleModel,op,bitvec,evaluate,verify
from puzzleops.symbolic import solve,analyze,capabilities,compare_hypotheses
from puzzleops.native_z3 import native_version,sexprs,value

HAS_Z3=native_version() is not None
BACKENDS=['reference']+(['z3'] if HAS_Z3 else [])

def rule(id,expr,**kwargs): return {'id':id,'expr':expr,**kwargs}
def model(constraints=None,**kwargs):
    return {'variables':{'x':{'lower':0,'upper':2},'y':{'lower':0,'upper':2}},
            'constraints':constraints or [],**kwargs}
def answers(result): return {json.dumps(x,sort_keys=True) for x in result['solutions']}

@pytest.mark.parametrize('backend',BACKENDS)
def test_projection_is_not_auxiliary_uniqueness(backend):
    m=model([rule('fixed',op('eq','x',1))],answer_variables=['x'])
    r=analyze(m,backend=backend)
    assert r['uniqueness']=='UNIQUE' and r['forced_values']=={'x':1}
    assert solve(m,backend=backend)['solutions']==[{'x':1}]
    m['answer_variables']=['x','y']
    r=analyze(m,backend=backend)
    assert r['uniqueness']=='MULTIPLE' and r['forced_values']=={'x':1} and r['not_forced']==['y']

@pytest.mark.parametrize('backend',BACKENDS)
def test_hypotheses_are_off_until_named(backend):
    m=model([rule('x1',op('eq','x',1),kind='hypothesis'),rule('x2',op('eq','x',2),kind='hypothesis')])
    assert len(solve(m,backend=backend)['solutions'])==9
    assert analyze(m,['x1'],backend)['forced_values']['x']==1
    assert analyze(m,['x1','x2'],backend)['status']=='UNSAT'
    assert analyze(m,['x2'],backend)['forced_values']['x']==2
    with pytest.raises(ValueError): solve(m,['nonexistent'],backend)
    with pytest.raises(ValueError): solve(m,['x1','x1'],backend)

@pytest.mark.parametrize('backend',BACKENDS)
def test_cores_are_sufficient_in_same_domain_context(backend):
    m=model([rule('small',op('le','x',0),sources=['clue:A']),
             rule('large',op('ge','x',2),kind='hypothesis',sources=['reading:B']),
             rule('unrelated',op('ge','y',0))])
    r=analyze(m,['large'],backend)
    assert r['status']=='UNSAT' and r['core_minimal'] is False
    core=r['unsat_core']; assert set(core)<={'small','large','unrelated'}
    subset=copy.deepcopy(m); subset['constraints']=[x for x in m['constraints'] if x['id'] in core]
    assert solve(subset,['large'] if 'large' in core else [],'reference')['status']=='UNSAT'
    assert r['core_sources']['small']==['clue:A']

@pytest.mark.parametrize('backend',BACKENDS)
def test_budget_never_becomes_unsat(backend):
    r=solve(model(),backend=backend,max_checks=1)
    assert r['status']=='SAT' and not r['complete'] and r['reason']=='solver_check_budget'
    a=analyze(model(),backend=backend,max_checks=1)
    assert a['status']=='SAT' and a['uniqueness']=='UNKNOWN' and not a['complete']
    with mock.patch('puzzleops.symbolic.Budget.remaining_ms',return_value=0):
        assert solve(model(),backend=backend)['status']=='UNKNOWN'

@pytest.mark.parametrize('backend',BACKENDS)
def test_exact_page_limit_is_checked_not_guessed(backend):
    r=solve(model(answer_variables=['x']),backend=backend,max_solutions=3)
    assert r['complete'] and len(r['solutions'])==3
    r=solve(model(answer_variables=['x']),backend=backend,max_solutions=2)
    assert not r['complete'] and len(r['solutions'])==2 and r['reason']=='max_solutions'

@pytest.mark.parametrize('backend',BACKENDS)
def test_empty_assignments_and_domains(backend):
    assert solve({'variables':{}},backend=backend)['solutions']==[{}]
    assert analyze({'variables':{}},backend=backend)['uniqueness']=='UNIQUE'
    assert solve({'variables':{},'constraints':[rule('false',False)]},backend=backend)['status']=='UNSAT'
    assert solve({'variables':{'x':{'values':[]}}},backend=backend)['status']=='UNSAT'
    assert analyze(model(answer_variables=[]),backend=backend)['uniqueness']=='UNIQUE'

@pytest.mark.parametrize('backend',BACKENDS)
def test_strict_booleans_and_conditional_arithmetic(backend):
    m={'variables':{'b':{'kind':'bool'},'n':{'lower':-2,'upper':2}},'constraints':[
        rule('meaning',op('eq','b',op('gt','n',0))),
        rule('conditional',op('eq',op('ite','b',op('mul',2,'n'),op('neg','n')),2))]}
    r=solve(m,backend=backend)
    assert answers(r)=={json.dumps(a,sort_keys=True) for a in [{'b':False,'n':-2},{'b':True,'n':1}]}
    assert not verify(m,{'b':0,'n':-2})['valid']

@pytest.mark.parametrize('backend',BACKENDS)
def test_bitvector_unsigned_wrap_and_shift(backend):
    m={'variables':{'x':{'kind':'bitvec','width':4}},'constraints':[
        rule('wrap',op('eq',op('bv_add','x',bitvec(1,4)),bitvec(0,4))),
        rule('unsigned',op('bv_ult',bitvec(3,4),'x'))]}
    r=analyze(m,backend=backend)
    assert r['uniqueness']=='UNIQUE' and r['assignment']['x']==15
    m['constraints']=[rule('overshift',op('eq',op('bv_shl','x',bitvec(8,4)),bitvec(0,4)))]
    assert len(solve(m,backend=backend)['solutions'])==16

@pytest.mark.parametrize('backend',BACKENDS)
def test_automaton_inside_negation_and_empty_sequence(backend):
    from puzzleops.automata import from_runs
    dfa=from_runs([2])['machine']
    m={'variables':{'x':{'lower':0,'upper':1},'y':{'lower':0,'upper':1}},
       'constraints':[rule('not_two',op('not',{'op':'automaton','vars':['x','y'],'machine':dfa}))]}
    assert len(solve(m,backend=backend)['solutions'])==3
    for runs,expected in [([],True),([1],False)]:
        m={'variables':{},'constraints':[rule('empty',{'op':'automaton','vars':[],'machine':from_runs(runs)['machine']})]}
        assert (solve(m,backend=backend)['status']=='SAT') is expected

@pytest.mark.parametrize('backend',BACKENDS)
def test_interpretations_propose_observation_not_acquire_it(backend):
    m=model([rule('readingA',op('eq','x',1),kind='hypothesis'),
             rule('readingB',op('eq','x',2),kind='hypothesis')],answer_variables=['x'])
    r=compare_hypotheses(m,{'A':['readingA'],'B':['readingB']},backend)
    assert r['distinguishing_observations']==[{'variable':'x','predictions':{'A':1,'B':2},'observation_acquired':False}]

@pytest.mark.parametrize('backend',BACKENDS)
def test_user_names_are_never_solver_code(backend):
    name='x) (assert false) (check-sat) ;'
    m={'variables':{name:{'values':[1,2]}},'constraints':[rule('";injection',op('eq',name,2))]}
    assert analyze(m,backend=backend)['assignment']=={name:2}
    export=run('symbolic.export',{'model':m})['result']
    assert name not in export['smt2'] and export['variable_mapping'][name]=='v0'

@pytest.mark.parametrize('bad',[
    {'op':'exec','args':['x']}, {'op':'eq','args':['missing',0]},
    {'op':'eq','args':['x',True]}, {'op':'mul','args':['x','y']},
    {'op':'eq','args':['x',0],'silent_extra':1}, {'op':'lt','args':[bitvec(1,4),bitvec(2,4)]},
    {'op':'eq','args':[bitvec(1,4),bitvec(1,8)]}, 1.0, None,
])
def test_malformed_or_ambiguous_ast_rejected(bad):
    with pytest.raises(ValueError): PuzzleModel.model_validate(model([rule('bad',bad)]))

def test_huge_bitvector_domain_does_not_allocate_or_overflow():
    m={'variables':{'x':{'kind':'bitvec','width':64}}}
    assert solve(m,backend='reference')['status']=='UNKNOWN'

def test_unavailable_backend_is_explicit_and_never_fallback():
    if capabilities()['backends']['cpsat']['available']: pytest.skip('CP-SAT installed; covered in integration tests')
    r=run('symbolic.solve',{'model':model(),'backend':'cpsat'})['result']
    assert r['status']=='UNAVAILABLE' and not r['complete'] and not r['solutions']

@pytest.mark.skipif(not HAS_Z3,reason='native Z3 is not available')
@pytest.mark.parametrize('seed',range(120))
def test_random_symbolic_models_match_exhaustive(seed):
    rng=random.Random(seed)
    names=['x','y','z']; variables={n:{'lower':-2,'upper':2} for n in names}
    predicates=[]
    for i in range(rng.randrange(1,5)):
        x,y=rng.sample(names,2)
        lhs=op('add',op('mul',rng.choice([-2,-1,1,2]),x),y)
        p=op(rng.choice(['eq','ne','lt','le','gt','ge']),lhs,rng.randrange(-4,5))
        if rng.random()<.4: p=op(rng.choice(['and','or','implies']),p,op('lt',x,y))
        predicates.append(rule(f'c{i}',p))
    if rng.random()<.3: predicates.append(rule('distinct',op('all_different',*names)))
    m={'variables':variables,'constraints':predicates,'answer_variables':rng.sample(names,rng.randrange(1,4))}
    ref=solve(m,backend='reference',max_solutions=200,max_checks=500,max_assignments=100000)
    z=solve(m,backend='z3',max_solutions=200,max_checks=500)
    assert ref['complete'] and z['complete']
    assert answers(ref)==answers(z)
    # Every result also has an independently checked full witness.
    assert all(verify(m,w)['valid'] for w in z['witnesses'])

@pytest.mark.skipif(not HAS_Z3,reason='native Z3 is not available')
@pytest.mark.parametrize('seed',range(30))
def test_random_bv_models_match_exhaustive(seed):
    rng=random.Random(seed); width=rng.randrange(1,6); maximum=(1<<width)-1
    m={'variables':{'x':{'kind':'bitvec','width':width}},'constraints':[
        rule('bits',op('bv_ule',op(rng.choice(['bv_xor','bv_add','bv_sub','bv_and','bv_or','bv_shl','bv_lshr']),
                               'x',bitvec(rng.randrange(maximum+1),width)),bitvec(rng.randrange(maximum+1),width)))]}
    assert answers(solve(m,backend='z3'))==answers(solve(m,backend='reference'))

def test_solver_output_parser():
    assert value(['-','4'])==-4
    assert value('#x0f')==15 and value(['_','bv3','4'])==3
    assert sexprs('((v0 true) (v1 (- 2)))')==[[['v0','true'],['v1',['-','2']]]]

def test_new_contracts_are_discoverable():
    assert find('unique forced')[0]['operation_id']=='symbolic.analyze'
    assert find('counterexample shortest')[0]['operation_id']=='automata.distinguish'
    assert find(operation_id='symbolic.solve')['cache_policy']=='never'
