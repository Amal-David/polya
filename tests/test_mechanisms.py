from itertools import product
import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from polya import run, find
from polya.mechanisms import scan
from examples.cryptic_demo import main, step


def setup():
    a=[step('encoding.symbol_map', {'mapping':{'a':x,'b':y}},rationale='explicit mapping')
       for x,y in [('4','1'),('5','2')]]
    b=[step('encoding.radix_bytes',{'radix':r},rationale='explicit radix') for r in [10,16]]
    return dict(source='ab',stages=[a,b],checkpoint={'kind':'prefix','value':'A','source':'test commitment'})


def test_scan_matches_naive_recipe_enumeration_and_memoizes():
    args=setup(); got=scan(**args)
    expected=[]
    for i,choices in enumerate(product(*args['stages'])):
        text=args['source']
        for s in choices:
            text=run(s['operation_id'],s['inputs']|{s['input_field']:text})['result'][s['output_field']]
        if text is not None and text.startswith('A'): expected.append((i,text))
    assert [(h['ordinal'],h['text']) for h in got['matches']]==expected
    assert got['complete'] and got['kernel_calls']==6 and got['cache_hits']==2
    assert len(got['trials'])==4


def test_duplicate_hypotheses_are_preserved_not_counted_independent():
    args=setup(); args['stages'][0].append(copy.deepcopy(args['stages'][0][0]))
    result=scan(**args)
    assert len(result['matches'])==2
    assert result['matches'][0]['ordinal']!=result['matches'][1]['ordinal']
    assert result['kernel_calls']==6


def test_resume_ranges_and_limits_do_not_claim_global_exhaustion():
    args=setup(); full=scan(**args)
    rows=[]
    for i in range(4):
        part=scan(**args,start=i,max_trials=1)
        rows+=part['trials']
        assert part['complete'] is False
    assert rows==full['trials']
    hit=scan(**args,max_matches=1)
    assert hit['termination_reason']=='match_limit' and not hit['complete']
    budget=scan(**args,max_work=1)
    assert budget['next_start']==0 and budget['trials']==[] and budget['termination_reason']=='work_limit'
    empty=scan(**args,start=4)
    assert empty['range_exhausted'] and not empty['complete']


def test_sha_checkpoint_utf8_and_full_public_receipt():
    args=setup();args['checkpoint']={'kind':'sha256','value':hashlib.sha256(b'A').hexdigest(),'source':'fixed test'}
    result=run('mechanism.scan',args)
    assert result['result']['matches'][0]['text']=='A'
    assert not result['receipt']['independently_reproduced']
    assert find(operation_id='mechanism.scan')['cache_policy']=='never'


def test_invalid_branches_remain_explicit():
    args=setup();args['source']='az'
    result=scan(**args)
    assert all(t['outcome']=='INVALID_RECIPE_INPUT' for t in result['trials'])
    assert result['matches']==[] and result['kernel_calls']==2


@pytest.mark.parametrize('mutation',[
    lambda a:a['stages'][0][0].update(operation_id='mechanism.scan'),
    lambda a:a['stages'][0][0].update(operation_id='os.system'),
    lambda a:a['stages'][0][0]['inputs'].update(text='conflicting'),
    lambda a:a['stages'][0][0].update(output_field='missing'),
    lambda a:a['stages'][0][0].update(input_field='missing'),
    lambda a:a['stages'][0][0]['inputs'].update(unknown=True),
    lambda a:a.update(stages=[[]]),
    lambda a:a.update(start=5),
    lambda a:a['checkpoint'].update(kind='sha256',value='not a hash'),
])
def test_invalid_specs_fail_before_search(mutation):
    args=setup();mutation(args)
    with pytest.raises(ValueError):scan(**args)


def test_clock_budget_keeps_resume_before_unfinished_recipe():
    args=setup()
    with patch('polya.mechanisms.time.monotonic',side_effect=[0,100]):
        result=scan(**args)
    assert result['termination_reason']=='time_limit'
    assert result['next_start']==0 and not result['complete']


def test_real_historical_checkpoints_and_unused_suffix():
    out=main()
    assert out['k1_unused_suffix_matches']
    grid=out['gsmg_spiral']
    assert len(grid['matches'])==1 and grid['matches'][0]['trace'][-1]['trailing_digits']=='0000'
    assert grid['kernel_calls']==56 and grid['cache_hits']==40


def test_kernel_contract_failure_is_not_a_negative_puzzle_result():
    from dataclasses import replace
    from puzzleops.catalog import REGISTRY
    bad=replace(REGISTRY['encoding.symbol_map'],kernel=lambda **kwargs:{'text':'bad'})
    with patch.dict(REGISTRY,{'encoding.symbol_map':bad}):
        with pytest.raises(RuntimeError,match='output contract'):
            scan(**setup())


def test_puzzle_vocabulary_discovers_applicable_tools_without_claiming_a_solve():
    ids={row['operation_id'] for row in find('gsmg',limit=20)}
    assert {'grid.traverse','cipher.bifid','cipher.checkerboard'} <= ids
