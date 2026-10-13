"""Budgeted active learning for deterministic resettable local Mealy systems.

The native observation-table learner is dependency-free. The optional AALpy path
uses the same guarded observations and bounded test oracle. Neither treats a
finite conformance test as a global equivalence oracle.
"""
from __future__ import annotations
from itertools import product
from typing import Protocol
import time

from .automata import Machine, Transition, as_machine, simulate, prepare_machine


class ResettableSystem(Protocol):
    def reset(self) -> None: ...
    def step(self,symbol: int | str) -> str: ...


class LearningBudgetExceeded(Exception): pass
class InconsistentObservations(Exception): pass


class LocalMachineSystem:
    """Opaque step/reset interface used by the learner, not its transition table."""
    def __init__(self,machine):
        self._machine=as_machine(machine)
        if self._machine.kind!='mealy': raise ValueError('active learning currently supports Mealy systems')
        self._table={(t.source,t.symbol):t for t in self._machine.transitions}
        self.reset()
    def reset(self): self._state=self._machine.initial
    def step(self,symbol):
        t=self._table[(self._state,symbol)]; self._state=t.target; return t.output


class GuardedQueries:
    def __init__(self,system,alphabet,max_queries,max_steps,timeout_ms,max_equivalence_tests):
        self.system=system; self.alphabet=alphabet
        self.max_queries,self.max_steps=max_queries,max_steps
        self.max_equivalence_tests=max_equivalence_tests
        self.start=time.monotonic(); self.deadline=self.start+timeout_ms/1000
        self.queries,self.steps,self.cache_hits,self.equivalence_tests=0,0,0,0
        self.observed={():()}; self.last_model=None; self.rounds=0
    def time_check(self):
        if time.monotonic()>=self.deadline: raise LearningBudgetExceeded('time_budget')
    def query(self,word,fresh=False):
        self.time_check(); word=tuple(word)
        if any(a not in self.alphabet for a in word): raise ValueError('query outside the declared alphabet')
        if not fresh and word in self.observed:
            self.cache_hits+=1; return self.observed[word]
        if self.queries>=self.max_queries: raise LearningBudgetExceeded('membership_query_budget')
        self.queries+=1; self.system.reset(); self.time_check()
        outputs=[]
        for i,a in enumerate(word):
            if self.steps>=self.max_steps: raise LearningBudgetExceeded('step_budget')
            self.time_check(); self.steps+=1
            out=self.system.step(a); self.time_check()
            if type(out) is not str or len(out)>1000:
                raise ValueError('system output must be a string of at most 1000 characters')
            outputs.append(out); prefix=word[:i+1]; observed=tuple(outputs)
            if prefix in self.observed and self.observed[prefix]!=observed:
                raise InconsistentObservations(f'Nonrepeatable outputs after reset for input prefix {prefix!r}')
            self.observed[prefix]=observed
        return tuple(outputs)
    def preflight(self):
        # Repeated singleton and two-step observations test reset behavior locally.
        for a in self.alphabet:
            for word in ((a,),(self.alphabet[0],a)):
                self.query(word,fresh=True); self.query(word,fresh=True)
    def counterexample(self,machine,max_depth):
        self.last_model=machine
        prepared = prepare_machine(machine)
        for depth in range(1,max_depth+1):
            for word in product(self.alphabet,repeat=depth):
                self.time_check()
                if self.equivalence_tests>=self.max_equivalence_tests:
                    raise LearningBudgetExceeded('equivalence_test_budget')
                self.equivalence_tests+=1
                observed=self.query(word)
                predicted=prepared.replay(list(word))['outputs']
                if tuple(predicted)!=observed: return word
        return None
    def stats(self):
        return {'physical_membership_queries':self.queries,'physical_steps':self.steps,
                'resets':self.queries,'cached_membership_queries':self.cache_hits,
                'equivalence_tests':self.equivalence_tests,'learning_rounds':self.rounds,
                'elapsed_ms':round((time.monotonic()-self.start)*1000,3)}


def native_lstar(queries,max_depth,max_rounds,max_states):
    """Mealy observation table with closure/consistency and counterexample prefixes."""
    alphabet=queries.alphabet; S=[()]; E=[(a,) for a in alphabet]
    while True:
        queries.time_check()
        if len(S)>4096 or len(E)>512:
            raise LearningBudgetExceeded('observation_table_budget')
        rows={}
        def row(s):
            if s not in rows:
                rows[s]=tuple(queries.query(s+e)[len(s):] for e in E)
            return rows[s]
        representatives={row(s):s for s in S}
        unclosed=None
        for s in list(S):
            for a in alphabet:
                if row(s+(a,)) not in representatives:
                    unclosed=s+(a,); break
            if unclosed is not None: break
        if unclosed is not None:
            S.append(unclosed); continue
        inconsistent=None
        for i,s in enumerate(S):
            for t in S[:i]:
                if row(s)!=row(t): continue
                for a in alphabet:
                    rs,rt=row(s+(a,)),row(t+(a,))
                    if rs!=rt:
                        suffix=next(e for e,x,y in zip(E,rs,rt) if x!=y)
                        inconsistent=(a,)+suffix; break
                if inconsistent is not None: break
            if inconsistent is not None: break
        if inconsistent is not None:
            if inconsistent in E: raise RuntimeError('Observation-table consistency failed to make progress')
            E.append(inconsistent); continue
        unique=list(dict.fromkeys(row(s) for s in S))
        if len(unique)>max_states: raise LearningBudgetExceeded('learned_state_budget')
        if queries.rounds>=max_rounds: raise LearningBudgetExceeded('learning_round_budget')
        queries.rounds+=1
        names={r:f'q{i}' for i,r in enumerate(unique)}
        edges=[]
        for r in unique:
            s=representatives[r]
            for a in alphabet:
                edges.append(Transition(source=names[r],symbol=a,target=names[row(s+(a,))],
                                        output=queries.query(s+(a,))[-1]))
        machine=Machine(kind='mealy',states=list(names.values()),alphabet=alphabet,
                        initial=names[row(())],transitions=edges)
        cex=queries.counterexample(machine,max_depth)
        if cex is None: return machine
        for i in range(1,len(cex)+1):
            prefix=cex[:i]
            if prefix not in S: S.append(prefix)


def aalpy_lstar(queries,max_depth,max_rounds,max_states):
    """Optional integration; deliberately a bounded conformance oracle, not exact EQ."""
    from aalpy.base import SUL,Oracle
    from aalpy.learning_algs import run_Lstar
    def export(hypothesis):
        states=list(hypothesis.states); names={s:f'q{i}' for i,s in enumerate(states)}
        if len(states)>max_states: raise LearningBudgetExceeded('learned_state_budget')
        return Machine(kind='mealy',states=list(names.values()),alphabet=queries.alphabet,
                       initial=names[hypothesis.initial_state],
                       transitions=[Transition(source=names[s],symbol=a,target=names[s.transitions[a]],
                                               output=s.output_fun[a]) for s in states for a in queries.alphabet])
    class Adapter(SUL):
        def __init__(self): super().__init__(); self.word=[]
        def pre(self): self.word=[]
        def post(self): pass
        def step(self,a):
            self.word.append(a)
            # Replaying a prefix through the guarded interface is intentional;
            # physical resets/steps are reported, not hidden as constant-time steps.
            return queries.query(self.word)[-1]
        def query(self,word): return list(queries.query(word))
    class BoundedOracle(Oracle):
        def __init__(self,sul): super().__init__(queries.alphabet,sul)
        def find_cex(self,hypothesis):
            queries.rounds+=1
            if queries.rounds>max_rounds: raise LearningBudgetExceeded('learning_round_budget')
            return queries.counterexample(export(hypothesis),max_depth)
    sul=Adapter(); oracle=BoundedOracle(sul)
    hypothesis=run_Lstar(queries.alphabet,sul,oracle,automaton_type='mealy',
                         max_learning_rounds=max_rounds,print_level=0)
    final=export(hypothesis)
    # Even when the library stops at its round limit, recheck the final hypothesis.
    if queries.counterexample(final,max_depth) is not None:
        raise LearningBudgetExceeded('round_limit_with_counterexample')
    return final


def learn_mealy(system:ResettableSystem,alphabet:list[int|str],learner='native',max_depth=5,
                max_queries=10000,max_steps=100000,max_equivalence_tests=10000,
                timeout_ms=10000,max_rounds=32,max_states=64):
    if type(alphabet) is not list or not 1<=len(alphabet)<=32 or len(set(alphabet))!=len(alphabet) or any(type(a) not in (str,int) for a in alphabet):
        raise ValueError('alphabet must contain 1-32 distinct string/integer symbols')
    for key,val,lo,hi in [('max_depth',max_depth,1,32),('max_queries',max_queries,1,100000),
                        ('max_steps',max_steps,1,1000000),('max_equivalence_tests',max_equivalence_tests,1,100000),
                        ('timeout_ms',timeout_ms,1,60000),('max_rounds',max_rounds,1,128),('max_states',max_states,1,256)]:
        if type(val) is not int or not lo<=val<=hi: raise ValueError(f'{key} must be in [{lo},{hi}]')
    if learner not in ('native','aalpy'): raise ValueError('learner must be native or aalpy')
    q=GuardedQueries(system,alphabet,max_queries,max_steps,timeout_ms,max_equivalence_tests)
    status,reason,machine='UNKNOWN',None,None
    try:
        if learner=='aalpy':
            try: import aalpy  # noqa: F401
            except ImportError:
                return {'status':'UNAVAILABLE','reason':'Install the learning extra from the source checkout to use AALpy.',
                        'machine':None,'learner':learner,'global_equivalence_proven':False,'complete':False,
                        'tested_max_depth':None,'stats':q.stats(),'scope':'No learning was performed.'}
        q.preflight()
        algorithm=native_lstar if learner=='native' else aalpy_lstar
        machine=algorithm(q,max_depth,max_rounds,max_states)
        status='BOUNDED_CONFORMANCE'
    except LearningBudgetExceeded as exc:
        status='BUDGET_EXHAUSTED'; reason=str(exc); machine=q.last_model
    except InconsistentObservations as exc:
        status='INCONSISTENT_OBSERVATIONS'; reason=str(exc); machine=None
    return {'status':status,'reason':reason,'machine':machine.model_dump() if machine else None,
            'learner':learner,'global_equivalence_proven':False,'complete':status=='BOUNDED_CONFORMANCE',
            'tested_max_depth':max_depth if status=='BOUNDED_CONFORMANCE' else None,'stats':q.stats(),
            'scope':'Only finite conformance under an assumed stationary, deterministic, resettable system. '
                    'Reset preflight is not a proof. Callback timeouts are cooperative, not process isolation.'}


def learn_local(machine,**kwargs):
    machine=as_machine(machine)
    result=learn_mealy(LocalMachineSystem(machine),machine.alphabet,**kwargs)
    result['scope']+=' This operation only queries the supplied local simulator; no live service is contacted.'
    return result
