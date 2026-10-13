"""0.2 operation contracts, kept out of the original primitive implementation."""
from typing import Literal
from pydantic import Field
from .automata import StrictModel,Machine,from_runs,simulate,distinguish
from .model import PuzzleModel,verify
from .symbolic import solve,analyze,compare_hypotheses,capabilities
from .learning import learn_local
from .native_z3 import Emitter
from .prepared import simulate_many

class Empty(StrictModel): pass
class ModelInput(StrictModel):
    model: PuzzleModel
    assumptions: list[str]=Field(default_factory=list,max_length=1024)
class ModelRunInput(ModelInput):
    backend: Literal['auto','z3','cpsat','reference']='auto'
    timeout_ms: int=Field(default=5000,ge=1,le=60000)
    max_checks: int=Field(default=1000,ge=1,le=10000)
    max_assignments: int=Field(default=100000,ge=1,le=1000000)
class SymbolicSolveInput(ModelRunInput):
    max_solutions: int=Field(default=100,ge=1,le=1000)
class VerifyModelInput(ModelInput):
    assignment: dict[str,int|bool]
class CompareInput(StrictModel):
    model: PuzzleModel
    cases: dict[str,list[str]]=Field(min_length=2,max_length=8)
    backend: Literal['auto','z3','cpsat','reference']='auto'
    timeout_ms: int=Field(default=5000,ge=1,le=60000)
    max_checks: int=Field(default=1000,ge=1,le=10000)
    max_assignments: int=Field(default=100000,ge=1,le=1000000)
class RunsInput(StrictModel):
    runs: list[int]=Field(max_length=64)
class ReplayInput(StrictModel):
    machine: Machine
    word: list[int|str]=Field(max_length=10000)
class ReplayManyInput(StrictModel):
    machine: Machine
    words: list[list[int|str]]=Field(max_length=256)

class DistinguishInput(StrictModel):
    left: Machine
    right: Machine
    max_pairs: int=Field(default=100000,ge=1,le=1000000)
    max_depth: int|None=Field(default=None,ge=0,le=10000)
    timeout_ms: int=Field(default=5000,ge=1,le=60000)
class LearnInput(StrictModel):
    machine: Machine
    learner: Literal['native','aalpy']='native'
    max_depth: int=Field(default=5,ge=1,le=32)
    max_queries: int=Field(default=10000,ge=1,le=100000)
    max_steps: int=Field(default=100000,ge=1,le=1000000)
    max_equivalence_tests: int=Field(default=10000,ge=1,le=100000)
    timeout_ms: int=Field(default=10000,ge=1,le=60000)
    max_rounds: int=Field(default=32,ge=1,le=128)
    max_states: int=Field(default=64,ge=1,le=256)

def export(model,assumptions):
    m=PuzzleModel.model_validate(model); active=m.active(assumptions); emitter=Emitter(m)
    return {'smt2':emitter.program(active)+'\n(check-sat)\n',
            'variable_mapping':emitter.names,'constraint_mapping':{f'k{i}':c.id for i,c in enumerate(active)},
            'scope':'Generated SMT-LIB for the supplied model; hypotheses omitted unless explicitly enabled.'}


def extension_ops(make):
    common={'backend':str,'backend_version':str|None,'active_constraint_ids':list[str],
            'enabled_hypotheses':list[str],'answer_variables':list[str],'stats':dict,'scope':str}
    return [
        make('automata.simulate_many','Replay a batch of sequences','Prepare a detached transition snapshot once for a bounded batch.',
             ReplayManyInput,simulate_many,'automata batch replay sequence prepared throughput',
             'Same exact deterministic-model replay as separate calls; not real-world observations.',
             '256 words, 10000 total symbols, standard output limit. No normalization or deduplication.',
             results=list[dict],word_count=int,symbol_count=int,scope=str),
        make('backends.inspect','Inspect available backends','Report runtime availability and supported capabilities.',
             Empty,capabilities,'backends capabilities z3 cpsat ortools learning aalpy offline',
             'Availability only, not a claim that an optional dependency passed integration tests.',
             'Local package/library inspection only.',cacheable=False,backends=dict,scope=str),
        make('symbolic.solve','Solve symbolic constraints','Enumerate projected answers and retain independently checked full witnesses.',
             SymbolicSolveInput,solve,'sat smt cp satisfiable symbolic boolean arithmetic bitvector enumerate',
             'Exact witnesses for the formal model. Complete only after enumeration exhaustion; UNKNOWN is not UNSAT.',
             '256 variables,1024 rules,20000 AST nodes; time,check,reference-work and output budgets.',cacheable=False,
             **common,status=Literal['SAT','UNSAT','UNKNOWN','UNAVAILABLE','UNSUPPORTED'],solutions=list[dict],witnesses=list[dict],complete=bool,reason=str|None,
             unsat_core=list[str]|None,core_minimal=bool),
        make('symbolic.analyze','Analyze uniqueness and consequences','Check projected uniqueness, forced values, and source-linked contradictions.',
             ModelRunInput,analyze,'sat smt unique ambiguity consequences forced contradiction unsat core assumptions',
             'Forced values require refutation of alternatives. Cores are sufficient, not guaranteed minimal; facts remain caller claims.',
             'Shared budget across all checks; auxiliary variables excluded from projected uniqueness.',cacheable=False,
             **common,status=Literal['SAT','UNSAT','UNKNOWN','UNAVAILABLE','UNSUPPORTED'],assignment=dict|None,alternative_assignment=dict|None,uniqueness=Literal['UNIQUE','MULTIPLE','UNKNOWN','UNSAT'],
             forced_values=dict,not_forced=list[str],undetermined=list[str],unsat_core=list[str]|None,
             core_minimal=bool,core_sources=dict,complete=bool,reason=str|None),
        make('symbolic.verify','Independently check an assignment','Evaluate every active constraint using a separate pure-Python interpreter.',
             VerifyModelInput,verify,'verify checker assignment witness symbolic',
             'Checks execution against the same formal model, not independent interpretation of the original clue.',
             'Requires a complete assignment; strict sorts and domains.',valid=bool,violated_domains=list[str],
             violated_constraints=list[str],checked_constraint_ids=list[str],scope=str),
        make('symbolic.export','Export a reproducible formal model','Export generated SMT-LIB and sanitized symbol/source mappings.',
             ModelInput,export,'export smtlib reproducibility inspect formal model',
             'Serialization only; no arbitrary code or raw SMT-LIB is accepted for execution.',
             'Same typed AST and admission limits.',smt2=str,variable_mapping=dict[str,str],constraint_mapping=dict[str,str],scope=str),
        make('hypotheses.compare','Compare competing interpretations','Analyze named assumption sets and propose differing forced observations.',
             CompareInput,compare_hypotheses,'hypothesis interpretation compare distinguish prediction experiment observation',
             'Proposed observations distinguish only the specified cases. No real observation is acquired.',
             '2-8 cases, with one shared time/check/reference budget. Empty suggestions do not mean equivalence.',cacheable=False,
             cases=dict,distinguishing_observations=list[dict],complete=bool,scope=str),
        make('automata.from_runs','Build a binary run-length rule','Construct a DFA from caller-specified consecutive filled-cell groups.',
             RunsInput,from_runs,'nonogram sequence run length binary pattern dfa',
             'Recognizes exactly the supplied positive run lengths, with optional leading/trailing zeros.',
             '64 runs, each <=128, at most1000 generated states.',machine=dict,scope=str),
        make('automata.simulate','Replay a deterministic model','Replay DFA acceptance or Mealy input/output behavior.',
             ReplayInput,simulate,'automata mealy dfa replay simulate transition state sequence',
             'Exact model replay; partial DFA edges reject, while Mealy machines must be total.',
             'At most10000 input symbols; validated deterministic transitions.',final_state=str|None,state_trace=list[str|None],
             outputs=list[str],accepted=bool|None,scope=str),
        make('automata.distinguish','Find a distinguishing experiment','Search the reachable product for a shortest distinguishing input sequence.',
             DistinguishInput,distinguish,'automata compare discriminate counterexample distinguish shortest experiment equivalence',
             'Witnesses are independently replayed. EQUIVALENT requires full reachable-product exhaustion; limits return UNKNOWN.',
             'Product-state,time,and optional depth budgets. Models only; no live queries.',cacheable=False,
             status=Literal['DISTINGUISHED','EQUIVALENT','UNKNOWN'],word=list[int|str]|None,left_replay=dict|None,right_replay=dict|None,expanded_pairs=int,
             discovered_pairs=int,shortest=bool|None,complete=bool,reason=str|None,scope=str),
        make('automata.learn_local','Learn a local hidden-state simulator','Learn a Mealy hypothesis through a guarded reset/step interface.',
             LearnInput,learn_local,'learning active lstar mealy state machine hidden rules aalpy reset query',
             'Finite conformance only, never global equivalence. Native learner is included; AALpy is optional.',
             'Only local simulator inputs via tools; membership,step,test,state,round,and cooperative time budgets.',cacheable=False,
             status=Literal['BOUNDED_CONFORMANCE','BUDGET_EXHAUSTED','INCONSISTENT_OBSERVATIONS','UNAVAILABLE','UNKNOWN'],reason=str|None,machine=dict|None,learner=str,global_equivalence_proven=bool,
             complete=bool,tested_max_depth=int|None,stats=dict,scope=str),
    ]
