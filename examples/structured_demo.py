"""Synthetic, cross-family demonstrations. Run: python -m examples.structured_demo"""
from __future__ import annotations
import json
import time
from polya import run
from polya.model import op,verify
from polya.automata import from_runs,distinguish


def nonogram():
    variables={f'c{i}_{j}':{'lower':0,'upper':1} for i in range(5) for j in range(5)}
    rules=[]
    for i,length in enumerate([1,3,5,3,1]):
        for axis in ('row','column'):
            names=[f'c{i}_{j}' if axis=='row' else f'c{j}_{i}' for j in range(5)]
            rules.append({'id':f'{axis}_{i}','expr':{'op':'automaton','vars':names,
                                                    'machine':from_runs([length])['machine']},
                          'sources':[f'synthetic:nonogram/{axis}/{i}']})
    return {'variables':variables,'constraints':rules}


def alphametic():
    # SEND + MORE = MONEY, keeping leading-zero exclusions explicit.
    variables={c:{'lower':0,'upper':9} for c in 'SENDMORY'}
    def word(s): return op('add',*[op('mul',10**i,c) for i,c in enumerate(reversed(s))])
    return {'variables':variables,'constraints':[
        {'id':'distinct_digits','expr':op('all_different',*variables)},
        {'id':'no_leading_zero_S','expr':op('ne','S',0)},
        {'id':'no_leading_zero_M','expr':op('ne','M',0)},
        {'id':'sum','expr':op('eq',op('add',word('SEND'),word('MORE')),word('MONEY'))}]}


def placement():
    names=[f'q{i}' for i in range(5)]
    return {'variables':{n:{'lower':0,'upper':4} for n in names},'constraints':[
        {'id':'columns','expr':op('all_different',*names)},
        {'id':'diagonal_up','expr':op('all_different',*[op('add',n,i) for i,n in enumerate(names)])},
        {'id':'diagonal_down','expr':op('all_different',*[op('sub',n,i) for i,n in enumerate(names)])}]}


def timing():
    return {'variables':{n:{'lower':0,'upper':12} for n in ['red','blue','green']},
            'constraints':[{'id':'red_first','expr':op('eq','red',0)},
                           {'id':'gap_3','expr':op('eq','blue',op('add','red',3))},
                           {'id':'gap_5','expr':op('eq','green',op('add','blue',5))}]}


def hypotheses():
    return {'variables':{'glyph':{'values':[3,8]},'auxiliary':{'lower':0,'upper':9}},
            'answer_variables':['glyph'],
            'constraints':[{'id':'reading_three','kind':'hypothesis','sources':['synthetic:glyph/readingA'],
                            'expr':op('eq','glyph',3)},
                           {'id':'reading_eight','kind':'hypothesis','sources':['synthetic:glyph/readingB'],
                            'expr':op('eq','glyph',8)}]}


def lock_machine():
    return {'kind':'mealy','states':['locked','armed'],'initial':'locked','alphabet':['tap','open'],
            'transitions':[{'source':'locked','symbol':'tap','target':'armed','output':'armed'},
                           {'source':'locked','symbol':'open','target':'locked','output':'denied'},
                           {'source':'armed','symbol':'tap','target':'locked','output':'reset'},
                           {'source':'armed','symbol':'open','target':'armed','output':'opened'}]}


def demonstrate():
    result={'scope':'Synthetic mechanism demonstrations, not real open-puzzle solutions or AI-agent speedup measurements.',
            'examples':{}}
    for name,model in [('word_arithmetic',alphametic()),('binary_visual_layout',nonogram()),('temporal_events',timing())]:
        start=time.perf_counter(); envelope=run('symbolic.analyze',{'model':model,'timeout_ms':15000})
        r=envelope['result']; r['end_to_end_ms']=round((time.perf_counter()-start)*1000,3)
        if r['status']!='SAT' or r['uniqueness']!='UNIQUE':
            raise AssertionError(f'{name}: demonstration did not establish uniqueness: {r}')
        assert verify(model,r['assignment'])['valid']
        result['examples'][name]=r
    model=placement()
    z=run('symbolic.solve',{'model':model,'backend':'z3','timeout_ms':15000})['result']
    ref=run('symbolic.solve',{'model':model,'backend':'reference','timeout_ms':15000})['result']
    assert z['complete'] and ref['complete'] and len(z['solutions'])==len(ref['solutions'])==10
    assert {tuple(a.values()) for a in z['solutions']}=={tuple(a.values()) for a in ref['solutions']}
    result['examples']['spatial_placement']={'z3':z,'exhaustive_reference':ref,
        'warning':'The generic reference enumerates anew for each projected answer. Timings are not a comparison with an optimized queens solver.'}
    hm=hypotheses()
    result['examples']['ambiguous_glyph']=run('hypotheses.compare',{'model':hm,
        'cases':{'three':['reading_three'],'eight':['reading_eight']}})['result']
    contradiction=run('symbolic.analyze',{'model':hm,'assumptions':['reading_three','reading_eight']})['result']
    assert contradiction['status']=='UNSAT'
    result['examples']['contradiction']=contradiction
    machine=lock_machine(); learned=run('automata.learn_local',{'machine':machine,'max_depth':5})['result']
    cross=distinguish(machine,learned['machine'])
    assert cross['status']=='EQUIVALENT'
    result['examples']['interactive_learning']={'learner_result':learned,'separate_exact_model_crosscheck':cross}
    return result


if __name__=='__main__': print(json.dumps(demonstrate(),indent=2))
