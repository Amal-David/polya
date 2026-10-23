"""Budgeted solve/analyze operations over one typed model and three backends."""
from __future__ import annotations
from importlib import metadata,util
from itertools import product
import math
import time
from .model import PuzzleModel, op, bitvec, evaluate, verify
from .native_z3 import Z3Engine, BackendUnavailable, UnsupportedModel, native_version

SCOPE='Results concern the supplied model and explicitly enabled hypotheses, not correctness of clue interpretation.'


class Budget:
    def __init__(self,timeout_ms,max_checks,max_assignments):
        self.start=time.monotonic(); self.deadline=self.start+timeout_ms/1000
        self.max_checks=max_checks; self.max_assignments=max_assignments
        self.checks=0; self.assignments=0; self.reason=None
    def remaining_ms(self): return max(0,math.ceil((self.deadline-time.monotonic())*1000))
    def begin_check(self):
        if self.checks>=self.max_checks: self.reason='solver_check_budget'; return None
        if not self.remaining_ms(): self.reason='time_budget'; return None
        self.checks+=1; return self.remaining_ms()
    def stats(self):
        return {'solver_checks':self.checks,'reference_assignments_checked':self.assignments,
                'elapsed_ms':round((time.monotonic()-self.start)*1000,3)}


class ReferenceEngine:
    name='reference'; version='0.2'
    def __init__(self,model,active,budget): self.model,self.active,self.budget=model,active,budget
    def check(self,extra):
        if self.budget.begin_check() is None: return {'status':'UNKNOWN','reason':self.budget.reason}
        domains=[v.domain() for v in self.model.variables.values()]
        # itertools.product eagerly pools inputs. Reject huge ranges before allocating them.
        if any((d.stop-d.start if isinstance(d,range) else len(d))>self.budget.max_assignments for d in domains):
            return {'status':'UNKNOWN','reason':'reference_domain_budget'}
        for values in product(*domains):
            if self.budget.assignments>=self.budget.max_assignments:
                return {'status':'UNKNOWN','reason':'reference_assignment_budget'}
            if not self.budget.remaining_ms(): return {'status':'UNKNOWN','reason':'time_budget'}
            self.budget.assignments+=1
            a=dict(zip(self.model.variables,values))
            if all(evaluate(c.expr,a,self.model.variables) for c in self.active) and all(evaluate(e,a,self.model.variables) for e in extra):
                return {'status':'SAT','assignment':a}
        return {'status':'UNSAT','core':[c.id for c in self.active],'core_minimal':False}
    def close(self): pass


def capabilities():
    def version(name):
        try: return metadata.version(name)
        except metadata.PackageNotFoundError: return None
    z3v=native_version()
    return {'backends':{
        'z3':{'available':z3v is not None,'version':z3v,'features':['boolean','integer_linear','bitvectors_unsigned','nested_dfa','unsat_core']},
        'cpsat':{'available':util.find_spec('ortools') is not None,'version':version('ortools'),
                 'features':['boolean','integer_linear','all_different','top_level_dfa'],
                 'unsupported':['bitvectors','nested_dfa']},
        'reference':{'available':True,'version':'0.2','features':['bounded_exhaustive','independent_evaluator']},
        'aalpy':{'available':util.find_spec('aalpy') is not None,'version':version('aalpy'),'features':['optional_active_mealy_learning']},
        'mcp':{'available':True,'version':'2025-06-18','features':['bundled_stdio_agent_transport']}},
        'scope':'Availability is not a validation certificate; see docs/history/results-0.2.md for actual test coverage.'}


def setup(model,assumptions,backend,timeout_ms,max_checks,max_assignments):
    m=PuzzleModel.model_validate(model)
    active=m.active(assumptions)
    if type(timeout_ms) is not int or not 1<=timeout_ms<=60000: raise ValueError('timeout_ms must be in [1,60000]')
    if type(max_checks) is not int or not 1<=max_checks<=10000: raise ValueError('max_checks must be in [1,10000]')
    if type(max_assignments) is not int or not 1<=max_assignments<=1_000_000: raise ValueError('max_assignments must be in [1,1000000]')
    b=Budget(timeout_ms,max_checks,max_assignments)
    if backend=='auto': backend='z3' if native_version() else 'reference'
    try:
        if backend=='z3': engine=Z3Engine(m,active,b)
        elif backend=='reference': engine=ReferenceEngine(m,active,b)
        elif backend=='cpsat':
            from .cpsat_backend import CPSATEngine
            engine=CPSATEngine(m,active,b)
        else: raise ValueError('backend must be auto, z3, cpsat or reference')
    except (BackendUnavailable,UnsupportedModel) as exc:
        return m,active,b,None,backend,exc
    return m,active,b,engine,backend,None


def literal(model,name,value):
    v=model.variables[name]
    return bitvec(value,v.width) if v.kind=='bitvec' else value


def blocking(model,assignment,names):
    return op('or',*[op('ne',n,literal(model,n,assignment[n])) for n in names])


def checked(engine,model,assumptions,extras):
    try: r=engine.check(extras)
    except UnsupportedModel as exc: return {'status':'UNSUPPORTED','reason':str(exc)}
    if r['status']=='SAT':
        v=verify(model,r['assignment'],assumptions)
        if not v['valid'] or not all(evaluate(e,r['assignment'],model.variables) for e in extras):
            raise RuntimeError('Backend witness failed independent Python verification')
    return r


def base_result(model,active,budget,backend,engine):
    return {'backend':backend,'backend_version':engine.version if engine else None,
            'active_constraint_ids':[c.id for c in active],
            'enabled_hypotheses':[c.id for c in active if c.kind=='hypothesis'],
            'answer_variables':model.projection,'stats':budget.stats(),'scope':SCOPE}


def solve(model:dict,assumptions:list[str] | None=None,backend='auto',max_solutions=100,
          timeout_ms=5000,max_checks=1000,max_assignments=100000):
    assumptions=[] if assumptions is None else assumptions
    if type(max_solutions) is not int or not 1<=max_solutions<=1000: raise ValueError('max_solutions must be in [1,1000]')
    m,active,b,e,backend,error=setup(model,assumptions,backend,timeout_ms,max_checks,max_assignments)
    if error:
        return {**base_result(m,active,b,backend,e),'status':'UNAVAILABLE' if isinstance(error,BackendUnavailable) else 'UNSUPPORTED',
                'solutions':[],'witnesses':[],'complete':False,'reason':str(error),'unsat_core':None,'core_minimal':False}
    sols=[]; witnesses=[]; extras=[]; complete=False; core=None; reason=None; status='UNKNOWN'
    try:
        while True:
            r=checked(e,m,assumptions,extras)
            if r['status']=='UNSAT':
                complete=True; status='SAT' if sols else 'UNSAT'
                if not sols: core=r.get('core',[])
                break
            if r['status']!='SAT':
                status='SAT' if sols else r['status']; reason=r.get('reason'); break
            # Probe one additional model so an exact-size page can still be certified complete.
            if len(sols)>=max_solutions:
                status='SAT'; reason='max_solutions'; break
            a=r['assignment']; witnesses.append(a)
            sols.append({n:a[n] for n in m.projection}); extras.append(blocking(m,a,m.projection))
        return {**base_result(m,active,b,backend,e),'status':status,'solutions':sols,'witnesses':witnesses,
                'complete':complete,'reason':reason,'unsat_core':core,'core_minimal':False}
    finally: e.close()


def analyze(model:dict,assumptions:list[str] | None=None,backend='auto',timeout_ms=5000,
            max_checks=1000,max_assignments=100000):
    assumptions=[] if assumptions is None else assumptions
    m,active,b,e,backend,error=setup(model,assumptions,backend,timeout_ms,max_checks,max_assignments)
    output={'status':'UNKNOWN','assignment':None,'alternative_assignment':None,'uniqueness':'UNKNOWN',
            'forced_values':{},'not_forced':[],'undetermined':list(m.projection),'unsat_core':None,
            'core_minimal':False,'core_sources':{},'complete':False,'reason':None}
    if error:
        output.update(status='UNAVAILABLE' if isinstance(error,BackendUnavailable) else 'UNSUPPORTED',reason=str(error))
        return {**base_result(m,active,b,backend,e),**output}
    try:
        first=checked(e,m,assumptions,[]); output['status']=first['status']
        if first['status']=='UNSAT':
            core=first.get('core',[])
            output.update(uniqueness='UNSAT',unsat_core=core,complete=True,undetermined=[],
                          core_sources={c.id:c.sources for c in active if c.id in core})
        elif first['status']=='SAT':
            a=first['assignment']; output['assignment']=a
            alternative=checked(e,m,assumptions,[blocking(m,a,m.projection)])
            if alternative['status']=='UNSAT':
                output.update(uniqueness='UNIQUE',forced_values={n:a[n] for n in m.projection},undetermined=[],complete=True)
            else:
                if alternative['status']=='SAT':
                    output.update(uniqueness='MULTIPLE',alternative_assignment=alternative['assignment'])
                else: output['reason']=alternative.get('reason')
                undetermined=[]
                for n in m.projection:
                    if alternative['status']=='SAT' and alternative['assignment'][n]!=a[n]:
                        output['not_forced'].append(n); continue
                    r=checked(e,m,assumptions,[blocking(m,a,[n])])
                    if r['status']=='UNSAT': output['forced_values'][n]=a[n]
                    elif r['status']=='SAT': output['not_forced'].append(n)
                    else: undetermined.append(n); output['reason']=r.get('reason')
                output['undetermined']=undetermined
                output['complete']=not undetermined and output['uniqueness']!='UNKNOWN'
        else: output['reason']=first.get('reason')
        return {**base_result(m,active,b,backend,e),**output}
    finally: e.close()


def compare_hypotheses(model:dict,cases:dict[str,list[str]],backend='auto',timeout_ms=5000,
                       max_checks=1000,max_assignments=100000):
    """Find conflicting forced predictions. Does not acquire the discriminating observation."""
    if not 2<=len(cases)<=8: raise ValueError('supply 2-8 named hypothesis cases')
    deadline=time.monotonic()+timeout_ms/1000; results={}; checks=max_checks; assignments=max_assignments
    for name,enabled in cases.items():
        remaining=max(0,int((deadline-time.monotonic())*1000))
        if remaining<=0 or checks<=0 or assignments<=0:
            results[name]={'status':'UNKNOWN','complete':False,'forced_values':{},'reason':'shared_budget'}
            continue
        r=analyze(model,enabled,backend,remaining,checks,assignments)
        results[name]=r
        checks-=r['stats']['solver_checks']; assignments-=r['stats']['reference_assignments_checked']
    experiments=[]; names=list(results)
    for i,a in enumerate(names):
        for z in names[i+1:]:
            ra,rz=results[a],results[z]
            if ra['status']!='SAT' or rz['status']!='SAT': continue
            for variable,av in ra['forced_values'].items():
                if variable in rz['forced_values'] and rz['forced_values'][variable]!=av:
                    experiments.append({'variable':variable,'predictions':{a:av,z:rz['forced_values'][variable]},
                                        'observation_acquired':False})
    failed_cases={name:r['status'] for name,r in results.items()
                  if r['status'] in ('UNAVAILABLE','UNSUPPORTED')}
    complete=all(r.get('complete',False) for r in results.values())
    return {'status':'EXECUTION_ERROR' if failed_cases else 'COMPLETE' if complete else 'PARTIAL',
            'failed_cases':failed_cases,'cases':results,'distinguishing_observations':experiments,
            'complete':complete,
            'scope':'Only differing forced values are proposed. An empty list does not prove cases equivalent; no evidence was acquired.'}
