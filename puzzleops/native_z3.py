"""Small stable-C-API bridge to Z3. Uses a z3-solver wheel or a system libz3.

Only our typed AST is translated; this module is not an arbitrary SMT-LIB tool.
There is no shell invocation. Each solver owns and closes a separate context.
"""
from __future__ import annotations
import ctypes as C
import ctypes.util
import importlib.util
from pathlib import Path
import re
from .model import bitvec, op


class BackendUnavailable(ValueError):
    pass


class UnsupportedModel(ValueError):
    pass


def library_path():
    spec=importlib.util.find_spec('z3')
    if spec and spec.submodule_search_locations:
        for root in spec.submodule_search_locations:
            for name in ('libz3.so','libz3.dylib','libz3.dll','z3.dll'):
                for p in (Path(root)/'lib'/name,Path(root)/name):
                    if p.is_file(): return str(p)
    return ctypes.util.find_library('z3')


def load_library():
    path=library_path()
    if not path: raise BackendUnavailable("Z3 is unavailable. Install the solvers extra from the source checkout.")
    try: lib=C.CDLL(path)
    except OSError as exc: raise BackendUnavailable(f'Cannot load Z3: {exc}') from exc
    for name,args,rest in [
        ('Z3_mk_config',[],C.c_void_p),('Z3_del_config',[C.c_void_p],None),
        ('Z3_mk_context',[C.c_void_p],C.c_void_p),('Z3_del_context',[C.c_void_p],None),
        ('Z3_eval_smtlib2_string',[C.c_void_p,C.c_char_p],C.c_char_p),
        ('Z3_get_error_msg',[C.c_void_p,C.c_uint],C.c_char_p),
        ('Z3_set_error_handler',[C.c_void_p,C.c_void_p],None),
        ('Z3_get_full_version',[],C.c_char_p)]:
        try:
            f=getattr(lib,name); f.argtypes=args; f.restype=rest
        except AttributeError as exc:
            raise BackendUnavailable('Installed libz3 lacks the supported C API') from exc
    return lib


def native_version():
    try: return load_library().Z3_get_full_version().decode()
    except BackendUnavailable: return None


def sexprs(text):
    tokens=re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+',text)
    stack=[]; forms=[]
    for t in tokens:
        if t=='(':
            v=[]
            if stack: stack[-1].append(v)
            else: forms.append(v)
            stack.append(v)
        elif t==')':
            if not stack: raise ValueError('Unbalanced solver output')
            stack.pop()
        elif stack: stack[-1].append(t)
        else: forms.append(t)
    if stack: raise ValueError('Unbalanced solver output')
    return forms


def value(node):
    if node=='true': return True
    if node=='false': return False
    if isinstance(node,list):
        if len(node)==2 and node[0]=='-': return -int(node[1])
        if len(node)==3 and node[0]=='_' and node[1].startswith('bv'): return int(node[1][2:])
        raise ValueError(f'Unsupported solver value: {node!r}')
    if node.startswith('#x'): return int(node[2:],16)
    if node.startswith('#b'): return int(node[2:],2)
    return int(node)


class Emitter:
    def __init__(self,model):
        self.model=model
        self.names={n:f'v{i}' for i,n in enumerate(model.variables)}

    def expression(self,e):
        if type(e) is bool: return 'true' if e else 'false'
        if type(e) is int: return str(e) if e>=0 else f'(- {-e})'
        if type(e) is str: return self.names[e]
        if 'bv' in e: return f"(_ bv{e['bv']} {e['width']})"
        name=e['op']
        if name=='automaton':
            from .automata import as_machine
            m=as_machine(e['machine']); ids={s:i for i,s in enumerate(m.states)}
            body='(or '+ ' '.join(f'(= a{len(e["vars"])} {ids[s]})' for s in m.accepting)+')'
            if not m.accepting: body='false'
            for i,n in reversed(list(enumerate(e['vars']))):
                nxt='(- 1)'
                for t in reversed(m.transitions):
                    nxt=f'(ite (and (= a{i} {ids[t.source]}) (= {self.names[n]} {self.expression(t.symbol)})) {ids[t.target]} {nxt})'
                body=f'(let ((a{i+1} {nxt})) {body})'
            return f'(let ((a0 {ids[m.initial]})) {body})'
        args=[self.expression(a) for a in e['args']]
        if name=='ne': return f'(not (= {args[0]} {args[1]}))'
        if name=='all_different' and len(args)<2: return 'true'
        if name in ('and','or') and not args: return 'true' if name=='and' else 'false'
        mapping={'eq':'=','lt':'<','le':'<=','gt':'>','ge':'>=','add':'+','sub':'-',
                 'mul':'*','neg':'-','and':'and','or':'or','not':'not','implies':'=>',
                 'xor':'xor','all_different':'distinct','ite':'ite','bv_and':'bvand',
                 'bv_or':'bvor','bv_xor':'bvxor','bv_not':'bvnot','bv_add':'bvadd',
                 'bv_sub':'bvsub','bv_shl':'bvshl','bv_lshr':'bvlshr',
                 'bv_ult':'bvult','bv_ule':'bvule'}
        return f'({mapping[name]} '+ ' '.join(args)+')'

    def program(self,active):
        out=['(set-option :print-success false)','(set-option :produce-models true)',
             '(set-option :produce-unsat-cores true)']
        for n,var in self.model.variables.items():
            sym=self.names[n]
            sort={'int':'Int','bool':'Bool'}.get(var.kind,f'(_ BitVec {var.width})')
            out.append(f'(declare-const {sym} {sort})')
            if var.kind=='bool': continue
            lit=lambda v:bitvec(v,var.width) if var.kind=='bitvec' else v
            if var.values is not None:
                dom=op('or',*[op('eq',n,lit(v)) for v in var.values])
            elif var.kind=='bitvec':
                dom=op('and',op('bv_ule',lit(var.lower),n),op('bv_ule',n,lit(var.upper)))
            else: dom=op('and',op('ge',n,var.lower),op('le',n,var.upper))
            out.append('(assert '+self.expression(dom)+')')
        for i,c in enumerate(active):
            out.append(f'(assert (! {self.expression(c.expr)} :named k{i}))')
        return '\n'.join(out)


class Z3Engine:
    name='z3'
    def __init__(self,model,active,budget):
        self.lib=load_library(); self.ctx=None; self.error=0
        self.version=self.lib.Z3_get_full_version().decode()
        self.model,self.active,self.budget=model,active,budget
        self.emitter=Emitter(model)
        cfg=self.lib.Z3_mk_config()
        self.ctx=self.lib.Z3_mk_context(cfg)
        self.lib.Z3_del_config(cfg)
        self.handler=C.CFUNCTYPE(None,C.c_void_p,C.c_uint)(self._error)
        self.lib.Z3_set_error_handler(self.ctx,self.handler)
        try: self.eval(self.emitter.program(active))
        except Exception:
            self.close(); raise

    def _error(self,ctx,code): self.error=code

    def eval(self,script):
        self.error=0
        result=self.lib.Z3_eval_smtlib2_string(self.ctx,script.encode())
        text=result.decode() if result else ''
        if self.error:
            msg=self.lib.Z3_get_error_msg(self.ctx,self.error).decode()
            raise ValueError('Z3 rejected the generated model: '+msg)
        if '(error ' in text: raise ValueError('Z3 rejected the generated model: '+text)
        return text.strip()

    def check(self,extra):
        remaining=self.budget.begin_check()
        if remaining is None: return {'status':'UNKNOWN','reason':self.budget.reason}
        self.eval(f'(set-option :timeout {remaining})\n(push 1)')
        try:
            for e in extra: self.eval('(assert '+self.emitter.expression(e)+')')
            status=self.eval('(check-sat)').splitlines()[-1].strip()
            if status=='sat':
                if self.emitter.names:
                    raw=self.eval('(get-value ('+' '.join(self.emitter.names.values())+'))')
                    vals={n:value(v) for n,v in sexprs(raw)[0]}
                    assignment={n:vals[s] for n,s in self.emitter.names.items()}
                else: assignment={}
                return {'status':'SAT','assignment':assignment}
            if status=='unsat':
                labels=sexprs(self.eval('(get-unsat-core)'))[0]
                core=[self.active[int(s[1:])].id for s in labels if s.startswith('k')]
                return {'status':'UNSAT','core':core,'core_minimal':False}
            reason=self.eval('(get-info :reason-unknown)')
            return {'status':'UNKNOWN','reason':reason}
        finally:
            self.eval('(pop 1)')

    def close(self):
        if self.ctx:
            self.lib.Z3_del_context(self.ctx); self.ctx=None
