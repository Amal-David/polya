"""Generated cross-family agent-evaluation cases and independent answer checks.

No model calls or claimed agent results. Metrics supplied by runners are not
trusted telemetry; retain external traces for audited comparisons.
"""
from __future__ import annotations
from collections import defaultdict
from itertools import groupby
import math
import random
from .catalog import canonical_json

FAMILIES=('text','spatial','temporal','sequence','logic','interactive')


def generate_cases(seed: int=0, per_family: int=10) -> list[dict]:
    if type(seed) is not int or type(per_family) is not int or not 1<=per_family<=100:
        raise ValueError('integer seed and 1-100 cases per family required')
    rng=random.Random(seed); cases=[]
    for i in range(per_family):
        rows,cols=rng.randrange(2,6),rng.randrange(2,6)
        cases.append(('text',{'rows':rows,'columns':cols,'text':''.join(rng.choice('ABc3éλ') for _ in range(rows*cols)),
                              'order':rng.choice(['row','column','row_snake','column_snake']),'reverse':bool(rng.randrange(2))},
                      'Return the specified traversal as a string. Indices count Unicode codepoints.'))
        cases.append(('spatial',{'n':rng.randrange(4,8)},'Return one queen column per row, zero-based, with no shared columns or diagonals.'))
        cases.append(('temporal',{'start':rng.randrange(-20,21),'gap1':rng.randrange(1,10),'gap2':rng.randrange(1,10)},
                      'Return [first,second,third] event times: first=start, second=first+gap1, third=second+gap2.'))
        row=[rng.randrange(2) for _ in range(rng.randrange(6,13))]
        runs=[len(list(g)) for value,g in groupby(row) if value==1]
        cases.append(('sequence',{'length':len(row),'runs':runs},'Return any binary row with exactly these consecutive filled runs.'))
        bits=[rng.randrange(2) for _ in range(8)]
        cases.append(('logic',{'size':8,'ones':sum(bits),'even_position_ones':sum(bits[::2])},
                      'Return a binary assignment with the specified total ones and ones at zero-based even positions.'))
        period=rng.randrange(2,8)
        cases.append(('interactive',{'period':period},
                      'Two resettable counters start at zero. read does not change state; tick increments. A emits state%period; B emits state%(period+1). Return a distinguishing sequence of read/tick inputs.'))
    return [{'id':f'{seed}:{family}:{idx}','family':family,'instance':instance,'prompt':prompt}
            for idx,(family,instance,prompt) in enumerate(cases)]


def _integers(answer,length):
    return type(answer) is list and len(answer)==length and all(type(v) is int for v in answer)


def check_answer(case: dict, answer) -> bool:
    """Checks are deliberately separate from operation implementations/solvers."""
    family=case['family'];v=case['instance']
    if len(canonical_json(answer).encode())>65536: return False
    if family=='text':
        if type(answer) is not str:return False
        r,c=v['rows'],v['columns'];order=v['order']
        coords=([(i,j) for i in range(r) for j in (range(c-1,-1,-1) if order=='row_snake' and i%2 else range(c))]
                if order in ('row','row_snake') else
                [(i,j) for j in range(c) for i in (range(r-1,-1,-1) if order=='column_snake' and j%2 else range(r))])
        expected=''.join(v['text'][i*c+j] for i,j in coords)
        return answer==(expected[::-1] if v['reverse'] else expected)
    if family=='spatial':
        n=v['n']
        return (_integers(answer,n) and all(0<=x<n for x in answer) and len(set(answer))==n
                and all(abs(answer[i]-answer[j])!=j-i for i in range(n) for j in range(i+1,n)))
    if family=='temporal':
        return _integers(answer,3) and answer==[v['start'],v['start']+v['gap1'],v['start']+v['gap1']+v['gap2']]
    if family=='sequence':
        return (_integers(answer,v['length']) and set(answer)<={0,1}
                and [len(list(g)) for b,g in groupby(answer) if b==1]==v['runs'])
    if family=='logic':
        return (_integers(answer,v['size']) and set(answer)<={0,1} and sum(answer)==v['ones']
                and sum(answer[::2])==v['even_position_ones'])
    if family=='interactive':
        if type(answer) is not list or not 1<=len(answer)<=32 or any(type(a) is not str or a not in ('read','tick') for a in answer):
            return False
        state=0
        for action in answer:
            state+=int(action=='tick')
            if state%v['period']!=state%(v['period']+1):return True
        return False
    raise ValueError('unknown evaluation family')


def score_records(cases: list[dict], records: list[dict]) -> dict:
    if len(cases)>600 or len(records)>1200:raise ValueError('evaluation size limit')
    by_id={c['id']:c for c in cases}
    if len(by_id)!=len(cases):raise ValueError('duplicate case IDs')
    observed={};metrics=defaultdict(list)
    for record in records:
        if type(record) is not dict or set(record)-{'case_id','condition','answer','metrics'}:
            raise ValueError('invalid evaluation record')
        key=(record.get('condition'),record.get('case_id'))
        if key[0] not in ('baseline','polya') or key[1] not in by_id or key in observed:
            raise ValueError('unknown condition/case or duplicate prediction')
        observed[key]=check_answer(by_id[key[1]],record.get('answer'))
        measure=record.get('metrics',{})
        if type(measure) is not dict or set(measure)-{'wall_ms','tokens','tool_calls'}:
            raise ValueError('unknown runner metric')
        for name,value in measure.items():
            if value is None:continue
            if type(value) not in (int,float) or not math.isfinite(value) or value<0:
                raise ValueError('metrics must be nonnegative finite numbers or null')
            metrics[(key[0],name)].append(value)
    results={}
    for condition in ('baseline','polya'):
        family_scores={}
        for family in FAMILIES:
            members=[c for c in cases if c['family']==family]
            correct=sum(observed.get((condition,c['id']),False) for c in members)
            family_scores[family]={'correct':correct,'total':len(members),
                                   'accuracy':correct/len(members) if members else None}
        ratios=[r['accuracy'] for r in family_scores.values() if r['accuracy'] is not None]
        results[condition]={'families':family_scores,'macro_accuracy':sum(ratios)/len(ratios) if ratios else None,
                            'submitted':sum(k[0]==condition for k in observed),
                            'missing':sum((condition,c['id']) not in observed for c in cases),
                            'metrics':{name:{'reported_count':len(metrics[(condition,name)]),
                                             'mean':sum(metrics[(condition,name)])/len(metrics[(condition,name)]) if metrics[(condition,name)] else None}
                                       for name in ('wall_ms','tokens','tool_calls')}}
    return {'conditions':results,'scope':'Synthetic supplied-rule tasks only. Missing predictions count as incorrect; no model was run by this scorer.',
            'metrics_are_runner_reported':True,'agent_speedup_established':False}
