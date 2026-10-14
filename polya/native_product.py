"""Experimental Rust kernel binding and algorithm-matched Python baseline.

Not an operation/backend default. Loading a native library is trusted local
configuration, not a capability exposed to puzzle input or MCP clients.
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
import ctypes as C
from pathlib import Path
import time
from .automata import simulate
from .prepared import prepare_machine


@dataclass(frozen=True)
class DensePair:
    nl: int
    nr: int
    k: int
    il: int
    ir: int
    alphabet: tuple
    lt: tuple[int, ...]
    lo: tuple[int, ...]
    rt: tuple[int, ...]
    ro: tuple[int, ...]


def prepare_pair(left, right) -> DensePair:
    l,r=prepare_machine(left),prepare_machine(right)
    if l.kind!='mealy' or r.kind!='mealy' or set(l.alphabet)!=set(r.alphabet):
        raise ValueError('experimental kernel requires total Mealy models with identical alphabets')
    outputs={v:i for i,v in enumerate(dict.fromkeys(x for m in (l,r) for row in m.emissions for x in row))}
    def flatten(m,table):
        return tuple(row[m.symbol_ids[a]] for row in table for a in l.alphabet)
    return DensePair(len(l.states),len(r.states),len(l.alphabet),l.initial,r.initial,l.alphabet,
                     flatten(l,l.targets),tuple(outputs[x] for x in flatten(l,l.emissions)),
                     flatten(r,r.targets),tuple(outputs[x] for x in flatten(r,r.emissions)))


def _limits(max_pairs,max_depth,timeout_ms):
    if type(max_pairs) is not int or not 1<=max_pairs<=1000000:
        raise ValueError('max_pairs must be in [1,1000000]')
    if max_depth is not None and (type(max_depth) is not int or not 0<=max_depth<=10000):
        raise ValueError('max_depth must be null or in [0,10000]')
    if type(timeout_ms) is not int or not 1<=timeout_ms<=60000:
        raise ValueError('timeout_ms must be in [1,60000]')


def python_product(p: DensePair, max_pairs=100000, max_depth=None, timeout_ms=5000):
    """Dense-array BFS matched to the Rust algorithm, not the original dict BFS."""
    _limits(max_pairs,max_depth,timeout_ms)
    deadline=time.monotonic()+timeout_ms/1000
    root=p.il*p.nr+p.ir
    parents=[-1]*(p.nl*p.nr); via=[0]*(p.nl*p.nr); parents[root]=root
    queue=[(root,0)];cursor=expanded=0;cutoff=False
    while cursor<len(queue):
        if time.monotonic()>=deadline:return 4,[],expanded,len(queue)
        pair,depth=queue[cursor];cursor+=1;expanded+=1
        if max_depth is not None and depth>=max_depth:cutoff=True;continue
        l,r=divmod(pair,p.nr)
        for a in range(p.k):
            if p.lo[l*p.k+a]!=p.ro[r*p.k+a]:
                word=[a];current=pair
                while current!=root:
                    if len(word)>=10000:return 6,[],expanded,len(queue)
                    word.append(via[current]);current=parents[current]
                return 1,word[::-1],expanded,len(queue)
            nxt=p.lt[l*p.k+a]*p.nr+p.rt[r*p.k+a]
            if parents[nxt]==-1:
                if len(queue)>=max_pairs:return 2,[],expanded,len(queue)
                parents[nxt]=pair;via[nxt]=a;queue.append((nxt,depth+1))
    return (3 if cutoff else 0),[],expanded,len(queue)


@lru_cache(maxsize=4)
def _library(path):
    lib=C.CDLL(str(Path(path).resolve(strict=True)))
    f=lib.polya_product
    u=C.c_uint32; ptr=C.POINTER(u)
    f.argtypes=[u,u,u,u,u,ptr,ptr,C.c_size_t,ptr,ptr,C.c_size_t,u,u,u,ptr,C.c_size_t,ptr]
    f.restype=C.c_int32
    return lib


def rust_product(p: DensePair, library_path: str, max_pairs=100000, max_depth=None, timeout_ms=5000):
    _limits(max_pairs,max_depth,timeout_ms)
    # The binding validates dimensions even for manually constructed DensePair values.
    if not isinstance(p,DensePair) or any(type(x) is not int for x in (p.nl,p.nr,p.k,p.il,p.ir)) or not (1<=p.nl<=1024 and 1<=p.nr<=1024 and 1<=p.k<=64):
        raise ValueError('invalid dense dimensions')
    arrays=(p.lt,p.lo,p.rt,p.ro)
    expected=(p.nl*p.k,p.nl*p.k,p.nr*p.k,p.nr*p.k)
    if not (0<=p.il<p.nl and 0<=p.ir<p.nr) or any(len(a)!=n for a,n in zip(arrays,expected)):
        raise ValueError('invalid dense indices or lengths')
    if any(type(x) is not int or not 0<=x<=0xffffffff for a in arrays for x in a):
        raise ValueError('dense entries must be uint32')
    if any(x>=p.nl for x in p.lt) or any(x>=p.nr for x in p.rt):
        raise ValueError('dense target outside domain')
    lt,lo,rt,ro=[(C.c_uint32*len(a))(*a) for a in arrays]
    word=(C.c_uint32*10000)();stats=(C.c_uint32*3)()
    code=_library(library_path).polya_product(p.nl,p.nr,p.k,p.il,p.ir,lt,lo,len(lt),rt,ro,len(rt),
        max_pairs,0xffffffff if max_depth is None else max_depth,timeout_ms,word,len(word),stats)
    if code==5 or code not in (0,1,2,3,4,6) or stats[2]>len(word):
        raise RuntimeError('native kernel returned an invalid result')
    return code,list(word[:stats[2]]),stats[0],stats[1]


def compare(left,right,*,backend='python',library_path=None,max_pairs=100000,max_depth=None,timeout_ms=5000):
    pair=prepare_pair(left,right)
    if backend=='python':result=python_product(pair,max_pairs,max_depth,timeout_ms)
    elif backend=='rust' and library_path is not None:
        result=rust_product(pair,library_path,max_pairs,max_depth,timeout_ms)
    else: raise ValueError('select python or rust with an explicit trusted library path')
    code,indices,expanded,discovered=result
    word=[pair.alphabet[i] for i in indices] if code==1 else None
    if word is not None and simulate(left,word)['outputs']==simulate(right,word)['outputs']:
        raise RuntimeError('native witness failed independent original replay')
    return {'status':'DISTINGUISHED' if code==1 else 'EQUIVALENT' if code==0 else 'UNKNOWN',
            'word':word,'expanded_pairs':expanded,'discovered_pairs':discovered,
            'complete':code in (0,1),'reason':{2:'product_pair_budget',3:'depth_budget',4:'time_budget',6:'witness_length_budget'}.get(code),
            'backend':backend,'scope':'Experimental supplied-model comparison only; no real observation acquired.'}
