"""Optional OR-Tools adapter; full integration tests require the solvers extra.

Top-level global constraints use CP-SAT's native all-different/automaton support.
Nested automata are explicitly unsupported, rather than silently mistranslated.
"""
from __future__ import annotations
from .model import expr_sort
from .native_z3 import BackendUnavailable, UnsupportedModel


class CPSATEngine:
    name='cpsat'
    def __init__(self,model,active,budget):
        try:
            from ortools.sat.python import cp_model
            import ortools
        except ImportError as exc:
            raise BackendUnavailable('CP-SAT is unavailable. Install the solvers extra from the source checkout.') from exc
        if any(v.kind=='bitvec' for v in model.variables.values()):
            raise UnsupportedModel('CP-SAT adapter does not support bit-vectors; choose z3 or reference.')
        self.cp,self.version=cp_model,ortools.__version__
        self.model,self.active,self.budget=model,active,budget

    def check(self,extra):
        remaining=self.budget.begin_check()
        if remaining is None: return {'status':'UNKNOWN','reason':self.budget.reason}
        cp=self.cp; m=cp.CpModel(); vv={}
        for name,var in self.model.variables.items():
            if var.kind=='bool': vv[name]=m.new_bool_var(name)
            elif var.values is not None:
                if not var.values:
                    vv[name]=m.new_int_var(0,0,name); m.add_bool_or([])
                else: vv[name]=m.new_int_var_from_domain(cp.Domain.from_values(var.values),name)
            else: vv[name]=m.new_int_var(var.lower,var.upper,name)
        serial=[0]
        def fresh():
            serial[0]+=1; return m.new_bool_var(f'aux_b_{serial[0]}')
        def inv(b): return not b if type(b) is bool else b.Not()
        def combine(args,is_and):
            if not args: return is_and
            b=fresh()
            if is_and:
                m.add_bool_and(args).only_enforce_if(b)
                m.add_bool_or([inv(x) for x in args]).only_enforce_if(b.Not())
            else:
                m.add_bool_or(args).only_enforce_if(b)
                m.add_bool_and([inv(x) for x in args]).only_enforce_if(b.Not())
            return b
        def bounds(e):
            if type(e) is int: return (e,e)
            if type(e) is str:
                v=self.model.variables[e]
                if v.kind=='bool': return (0,1)
                return (min(v.values or [0]),max(v.values or [0])) if v.values is not None else (v.lower,v.upper)
            name=e['op']; bs=[bounds(a) for a in (e['args'][1:] if name=='ite' else e['args'])]
            if name=='add': lo,hi=sum(x[0] for x in bs),sum(x[1] for x in bs)
            elif name=='sub': lo,hi=bs[0][0]-bs[1][1],bs[0][1]-bs[1][0]
            elif name=='neg': lo,hi=-bs[0][1],-bs[0][0]
            elif name=='mul':
                vals=[a*b for a in bs[0] for b in bs[1]]; lo,hi=min(vals),max(vals)
            elif name=='ite': lo,hi=min(x[0] for x in bs),max(x[1] for x in bs)
            else: raise UnsupportedModel('Cannot bound CP-SAT arithmetic expression')
            if max(abs(lo),abs(hi))>=2**59:
                raise UnsupportedModel('CP-SAT expression may overflow safe integer bounds; choose z3.')
            return lo,hi
        def expr(e):
            if type(e) in (bool,int): return e
            if type(e) is str: return vv[e]
            if 'bv' in e or e.get('op','').startswith('bv_'):
                raise UnsupportedModel('Bit-vectors require z3 or reference.')
            name=e['op']
            if name=='automaton':
                raise UnsupportedModel('Nested automaton constraints require z3 or reference.')
            args=[expr(a) for a in e['args']]
            if name in ('add','sub','neg','mul'):
                bounds(e)
                if name=='add': return sum(args)
                if name=='sub': return args[0]-args[1]
                if name=='neg': return -args[0]
                return args[0]*args[1]
            if name=='ite':
                cond,a,b=args
                if type(cond) is bool: return a if cond else b
                if expr_sort(e,self.model.variables)=='bool':
                    return combine([combine([cond,a],True),combine([inv(cond),b],True)],False)
                lo,hi=bounds(e); serial[0]+=1
                out=m.new_int_var(lo,hi,f'aux_i_{serial[0]}')
                m.add(out==a).only_enforce_if(cond); m.add(out==b).only_enforce_if(inv(cond))
                return out
            if name=='not': return inv(args[0])
            if name in ('and','or'): return combine(args,name=='and')
            if name=='implies': return combine([inv(args[0]),args[1]],False)
            if name=='xor': return combine([combine([args[0],inv(args[1])],True),combine([inv(args[0]),args[1]],True)],False)
            if name=='all_different':
                return combine([comparison('ne',args[i],args[j]) for i in range(len(args)) for j in range(i)],True)
            return comparison(name,*args)
        def comparison(name,a,b):
            comparisons={'eq':lambda:a==b,'ne':lambda:a!=b,'lt':lambda:a<b,'le':lambda:a<=b,
                         'gt':lambda:a>b,'ge':lambda:a>=b}
            opposite={'eq':'ne','ne':'eq','lt':'ge','le':'gt','gt':'le','ge':'lt'}
            if name not in comparisons: raise UnsupportedModel(f'CP-SAT does not support {name}')
            v=fresh()
            m.add(comparisons[name]()).only_enforce_if(v)
            m.add(comparisons[opposite[name]]()).only_enforce_if(v.Not())
            return v
        def add(e):
            if isinstance(e,dict) and e.get('op')=='and':
                for x in e['args']: add(x)
            elif isinstance(e,dict) and e.get('op')=='all_different' and all(expr_sort(x,self.model.variables)=='int' for x in e['args']):
                if len(e['args'])>1: m.add_all_different([expr(a) for a in e['args']])
            elif isinstance(e,dict) and e.get('op')=='automaton':
                from .automata import as_machine
                machine=as_machine(e['machine']); ids={s:i for i,s in enumerate(machine.states)}
                if not e['vars']:
                    m.add_bool_or([machine.initial in machine.accepting])
                elif not machine.accepting or not machine.transitions:
                    m.add_bool_or([])
                else:
                    m.add_automaton([vv[n] for n in e['vars']],ids[machine.initial],
                                    [ids[s] for s in machine.accepting],
                                    [(ids[t.source],t.symbol,ids[t.target]) for t in machine.transitions])
            else: m.add_bool_or([expr(e)])
        for c in self.active: add(c.expr)
        for e in extra: add(e)
        problem=m.validate()
        if problem: raise UnsupportedModel('CP-SAT model validation: '+problem)
        remaining=self.budget.remaining_ms()
        if remaining<=0: return {'status':'UNKNOWN','reason':'time_budget'}
        solver=cp.CpSolver(); solver.parameters.max_time_in_seconds=remaining/1000
        solver.parameters.num_search_workers=1; solver.parameters.random_seed=0
        status=solver.solve(m)
        if status in (cp.OPTIMAL,cp.FEASIBLE):
            assignment={n:bool(solver.value(v)) if self.model.variables[n].kind=='bool' else int(solver.value(v)) for n,v in vv.items()}
            return {'status':'SAT','assignment':assignment}
        if status==cp.INFEASIBLE:
            return {'status':'UNSAT','core':[c.id for c in self.active],'core_minimal':False}
        if status==cp.MODEL_INVALID: raise UnsupportedModel('CP-SAT rejected the generated model')
        return {'status':'UNKNOWN','reason':solver.status_name(status)}

    def close(self): pass
