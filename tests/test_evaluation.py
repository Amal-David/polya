from itertools import permutations,product
import pytest
from polya import run
from polya.evaluation import generate_cases,check_answer,score_records,FAMILIES


def witness(case):
    v=case['instance'];f=case['family']
    if f=='text':return run('grid.read',v)['result']['text']
    if f=='spatial':return next(list(p) for p in permutations(range(v['n'])) if check_answer(case,list(p)))
    if f=='temporal':return [v['start'],v['start']+v['gap1'],v['start']+v['gap1']+v['gap2']]
    if f=='interactive':return ['tick']*v['period']
    n=v['length'] if f=='sequence' else v['size']
    return next(list(p) for p in product((0,1),repeat=n) if check_answer(case,list(p)))


@pytest.mark.parametrize('seed',range(6))
def test_all_families_have_valid_witnesses_and_reject_empty_answers(seed):
    cases=generate_cases(seed,2)
    assert {c['family'] for c in cases}==set(FAMILIES)
    for case in cases:
        assert check_answer(case,witness(case))
        assert not check_answer(case,None)


def test_balanced_scoring_missing_answers_and_no_invented_metrics():
    cases=generate_cases(5,1)
    records=[{'condition':'polya','case_id':c['id'],'answer':witness(c)} for c in cases]
    r=score_records(cases,records)
    assert r['conditions']['polya']['macro_accuracy']==1
    assert r['conditions']['baseline']['missing']==6
    assert r['conditions']['baseline']['macro_accuracy']==0
    assert r['conditions']['polya']['metrics']['tokens']['mean'] is None
    assert not r['agent_speedup_established']
    with pytest.raises(ValueError):score_records(cases,records+[records[0]])
    bad={**records[0],'metrics':{'wall_ms':float('nan')}}
    with pytest.raises(ValueError):score_records(cases,[bad])
