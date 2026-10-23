"""Strict, non-executable JSON intermediate representation plus a separate evaluator.

String expressions refer to variables. Integer and boolean literals remain distinct.
Symbolic word candidates should be mapped explicitly to integers by the caller.
"""
from __future__ import annotations

from typing import Literal
from pydantic import Field, JsonValue, ValidationError, model_validator
from .automata import StrictModel, Machine, simulate

LIMIT=10**12


class Variable(StrictModel):
    kind: Literal['int','bool','bitvec']='int'
    lower: int | None=Field(default=None,description='Inclusive integer lower bound; supply both bounds OR values. Bounds are caller assumptions, never inferred.')
    upper: int | None=Field(default=None,description='Inclusive integer upper bound; supply both bounds OR values. Each integer bound must be within +/-10^12.')
    values: list[int] | None=Field(default=None,max_length=10000,description='Explicit distinct integer domain instead of bounds; [] is an empty domain, not an unknown domain.')
    width: int | None=Field(default=None,ge=1,le=64)

    @model_validator(mode='after')
    def validate_domain(self):
        if self.kind=='bool':
            if any(x is not None for x in (self.lower,self.upper,self.values,self.width)):
                raise ValueError('bool variables have no numeric domain fields')
            return self
        if self.kind=='bitvec':
            if self.width is None:
                raise ValueError('bitvec requires explicit width')
        elif self.width is not None:
            raise ValueError('width only applies to bitvec')
        if self.values is not None:
            if self.lower is not None or self.upper is not None:
                raise ValueError('use values OR inclusive bounds')
            if len(set(self.values))!=len(self.values):
                raise ValueError('domain values must be distinct')
            numbers=self.values
        else:
            if self.kind=='bitvec' and self.lower is None and self.upper is None:
                self.lower,self.upper=0,(1<<self.width)-1
            if self.lower is None or self.upper is None or self.lower>self.upper:
                raise ValueError('numeric variables require non-reversed inclusive bounds or values')
            numbers=[self.lower,self.upper]
        if self.kind=='bitvec':
            if any(not 0<=n<(1<<self.width) for n in numbers):
                raise ValueError('bitvec values must be unsigned and fit their width')
        elif any(abs(n)>LIMIT for n in numbers):
            raise ValueError('integer domain exceeds admission limit')
        return self

    @property
    def sort(self):
        return f'bv{self.width}' if self.kind=='bitvec' else self.kind

    def contains(self,value):
        if self.kind=='bool': return type(value) is bool
        if type(value) is not int: return False
        return value in self.values if self.values is not None else self.lower<=value<=self.upper

    def domain(self):
        if self.kind=='bool': return [False,True]
        return self.values if self.values is not None else range(self.lower,self.upper+1)


class Rule(StrictModel):
    id: str=Field(min_length=1,max_length=100)
    expr: JsonValue
    kind: Literal['observation','hypothesis','derived']='observation'
    sources: list[str]=Field(default_factory=list,max_length=32)
    note: str=Field(default='',max_length=2000)


class PuzzleModel(StrictModel):
    variables: dict[str,Variable]=Field(max_length=256)
    constraints: list[Rule]=Field(default_factory=list,max_length=1024)
    answer_variables: list[str] | None=None

    @model_validator(mode='after')
    def validate_model(self):
        if any(not n or len(n)>100 for n in self.variables):
            raise ValueError('variable names must contain 1-100 characters')
        ids=[c.id for c in self.constraints]
        if len(ids)!=len(set(ids)): raise ValueError('constraint ids must be unique')
        if self.answer_variables is not None:
            if len(set(self.answer_variables))!=len(self.answer_variables) or not set(self.answer_variables)<=set(self.variables):
                raise ValueError('answer_variables must be distinct declared variables')
        nodes=[0]
        errors=[]
        for index,c in enumerate(self.constraints):
            try:
                if expr_sort(c.expr,self.variables,nodes=nodes)!='bool':
                    raise ValueError('constraint must be boolean')
            except ValueError as exc:
                errors.append({'type':'value_error','loc':('constraints',index,'expr'),
                               'input':c.expr,'ctx':{'error':ValueError(f'constraint {c.id!r}: {exc}')}})
        if errors:
            raise ValidationError.from_exception_data(type(self).__name__,errors)
        return self

    def active(self,assumptions: list[str]):
        ids={c.id for c in self.constraints if c.kind=='hypothesis'}
        if len(set(assumptions))!=len(assumptions) or not set(assumptions)<=ids:
            raise ValueError('assumptions must be distinct ids of declared hypotheses')
        return [c for c in self.constraints if c.kind!='hypothesis' or c.id in assumptions]

    @property
    def projection(self):
        return list(self.variables) if self.answer_variables is None else self.answer_variables


def op(name: str,*args):
    return {'op':name,'args':list(args)}


def bitvec(value: int,width: int):
    return {'bv':value,'width':width}


def expr_sort(e,variables,depth=0,nodes=None):
    nodes=[0] if nodes is None else nodes
    nodes[0]+=1
    if depth>32 or nodes[0]>20000: raise ValueError('expression nesting/node budget exceeded')
    if type(e) is bool: return 'bool'
    if type(e) is int:
        if abs(e)>LIMIT: raise ValueError('integer literal exceeds admission limit')
        return 'int'
    if type(e) is str:
        if e not in variables: raise ValueError(f'undeclared variable: {e!r}')
        return variables[e].sort
    if type(e) is not dict: raise ValueError('expression must be an integer, boolean, variable name, or AST object')
    if set(e)=={'bv','width'}:
        if type(e['bv']) is not int or type(e['width']) is not int or not 1<=e['width']<=64 or not 0<=e['bv']<(1<<e['width']):
            raise ValueError('invalid unsigned bit-vector literal')
        return f"bv{e['width']}"
    if e.get('op')=='automaton':
        if set(e)!={'op','vars','machine'} or type(e['vars']) is not list or len(e['vars'])>256:
            raise ValueError('automaton requires vars and machine, at most 256 sequence variables')
        if any(type(v) is not str or v not in variables or variables[v].sort!='int' for v in e['vars']):
            raise ValueError('automaton labels require declared integer variables')
        m=Machine.model_validate(e['machine'])
        if m.kind!='dfa' or any(type(a) is not int or abs(a)>LIMIT for a in m.alphabet):
            raise ValueError('sequence constraints require a DFA with integer labels')
        if len(e['vars'])*max(1,len(m.transitions))>100000:
            raise ValueError('automaton unrolling exceeds admission limit')
        return 'bool'
    if set(e)!={'op','args'} or type(e['op']) is not str or type(e['args']) is not list or len(e['args'])>512:
        raise ValueError('operation must contain exactly op and an args array')
    name,args=e['op'],e['args']
    ss=[expr_sort(a,variables,depth+1,nodes) for a in args]
    def require(ok,message):
        if not ok: raise ValueError(f'{name}: {message}')
    if name in ('eq','ne'):
        require(len(ss)==2 and ss[0]==ss[1],'requires two operands of identical sorts'); return 'bool'
    if name in ('lt','le','gt','ge'):
        require(ss==['int','int'],'requires two integers; use bv_ult/bv_ule for unsigned bit-vectors'); return 'bool'
    if name in ('add','mul','sub'):
        require(len(ss)>=1 and all(s=='int' for s in ss),'requires integer operands')
        if name=='sub': require(len(ss)==2,'requires two operands')
        if name=='mul': require(len(args)==2 and any(type(a) is int for a in args),'requires multiplication by an integer literal')
        return 'int'
    if name=='neg': require(ss==['int'],'requires one integer'); return 'int'
    if name in ('and','or'):
        require(all(s=='bool' for s in ss),'requires boolean operands'); return 'bool'
    if name=='not': require(ss==['bool'],'requires one boolean'); return 'bool'
    if name in ('implies','xor'):
        require(ss==['bool','bool'],'requires two booleans'); return 'bool'
    if name=='all_different':
        require(not ss or (len(set(ss))==1),'requires operands of identical sorts'); return 'bool'
    if name=='ite':
        require(len(ss)==3 and ss[0]=='bool' and ss[1]==ss[2],'requires condition and two same-sort branches'); return ss[1]
    if name in ('bv_and','bv_or','bv_xor','bv_add','bv_sub','bv_shl','bv_lshr','bv_ult','bv_ule'):
        require(len(ss)==2 and ss[0]==ss[1] and ss[0].startswith('bv'),'requires same-width bit-vectors')
        return 'bool' if name in ('bv_ult','bv_ule') else ss[0]
    if name=='bv_not':
        require(len(ss)==1 and ss[0].startswith('bv'),'requires one bit-vector'); return ss[0]
    raise ValueError(f'unsupported expression operation: {name}')


def evaluate(e,assignment,variables):
    """Pure Python interpretation, independent of solver compilation."""
    if type(e) in (bool,int): return e
    if type(e) is str: return assignment[e]
    if 'bv' in e: return e['bv']
    name=e['op']
    if name=='automaton':
        word=[assignment[v] for v in e['vars']]
        m=Machine.model_validate(e['machine'])
        if any(a not in m.alphabet for a in word): return False
        return simulate(m,word)['accepted']
    args=e['args']; a=[evaluate(x,assignment,variables) for x in args]
    if name=='eq': return a[0]==a[1]
    if name=='ne': return a[0]!=a[1]
    if name=='lt': return a[0]<a[1]
    if name=='le': return a[0]<=a[1]
    if name=='gt': return a[0]>a[1]
    if name=='ge': return a[0]>=a[1]
    if name=='add': return sum(a)
    if name=='mul': return a[0]*a[1]
    if name=='sub': return a[0]-a[1]
    if name=='neg': return -a[0]
    if name=='and': return all(a)
    if name=='or': return any(a)
    if name=='not': return not a[0]
    if name=='implies': return not a[0] or a[1]
    if name=='xor': return a[0]!=a[1]
    if name=='all_different': return len(set(a))==len(a)
    if name=='ite': return a[1] if a[0] else a[2]
    if name=='bv_ult': return a[0]<a[1]
    if name=='bv_ule': return a[0]<=a[1]
    width=int(expr_sort(args[0],variables)[2:]); mask=(1<<width)-1
    if name=='bv_and': return a[0]&a[1]
    if name=='bv_or': return a[0]|a[1]
    if name=='bv_xor': return a[0]^a[1]
    if name=='bv_add': return (a[0]+a[1])&mask
    if name=='bv_sub': return (a[0]-a[1])&mask
    if name=='bv_not': return (~a[0])&mask
    if name=='bv_shl': return 0 if a[1]>=width else (a[0]<<a[1])&mask
    if name=='bv_lshr': return 0 if a[1]>=width else a[0]>>a[1]
    raise ValueError('unsupported expression')


def verify(model: dict | PuzzleModel,assignment: dict,assumptions: list[str] | None=None):
    m=model if isinstance(model,PuzzleModel) else PuzzleModel.model_validate(model)
    active=m.active(assumptions or [])
    if type(assignment) is not dict or set(assignment)!=set(m.variables):
        raise ValueError('verification requires one value for every declared variable, and no extras')
    domains=[n for n,v in m.variables.items() if not v.contains(assignment[n])]
    failed=[] if domains else [c.id for c in active if not evaluate(c.expr,assignment,m.variables)]
    return {'valid':not domains and not failed,'violated_domains':domains,'violated_constraints':failed,
            'checked_constraint_ids':[c.id for c in active],
            'scope':'Independent Python evaluation of the supplied formal model; not independent validation of clue interpretation.'}
