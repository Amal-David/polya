"""Reproducible ablations; correctness asserted, timings never CI thresholds."""
import argparse
from itertools import product
import json
from pathlib import Path
import platform
import statistics
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from polya import run
from polya.automata import Machine,simulate,distinguish
from polya.prepared import prepare_machine,simulate_many
from polya.native_product import prepare_pair,python_product,rust_product,compare
from polya.native_z3 import native_version


def measure(fn,repeats):
    fn();samples=[]
    for _ in range(repeats):
        start=time.perf_counter();fn();samples.append((time.perf_counter()-start)*1000)
    return {'samples_ms':samples,'median_ms':statistics.median(samples)}


def main():
    p=argparse.ArgumentParser();p.add_argument('--rust-lib');p.add_argument('--repeats',type=int,default=7)
    p.add_argument('--output',type=Path);a=p.parse_args()
    if not 3<=a.repeats<=30:raise ValueError('repeats must be in [3,30]')
    raw={'kind':'mealy','states':[f'q{i}' for i in range(128)],'alphabet':['a','b'],'initial':'q0',
         'transitions':[{'source':f'q{i}','symbol':s,'target':f'q{(i+1)%128}','output':str(i%3)} for i in range(128) for s in ['a','b']]}
    machine=Machine.model_validate(raw);words=[list(w) for w in product('ab',repeat=8)];prepared=prepare_machine(machine)
    expected=[simulate(machine,w) for w in words]
    assert [prepared.simulate(w) for w in words]==simulate_many(raw,words)['results']==expected
    replay={'individual_kernel':measure(lambda:[simulate(machine,w) for w in words],a.repeats),
            'prepared_kernel':measure(lambda:[prepared.simulate(w) for w in words],a.repeats),
            'batch_public_api':measure(lambda:run('automata.simulate_many',{'machine':raw,'words':words}),a.repeats),
            'individual_public_api':measure(lambda:[run('automata.simulate',{'machine':raw,'word':w}) for w in words],a.repeats)}
    # Coprime cycles, constant outputs: reachable product really has 200*199 pairs.
    def cycle(n):return {'kind':'mealy','states':[str(i) for i in range(n)],'alphabet':['step'],'initial':'0',
                        'transitions':[{'source':str(i),'symbol':'step','target':str((i+1)%n),'output':'x'} for i in range(n)]}
    left,right=cycle(200),cycle(199);pair=prepare_pair(left,right)
    assert distinguish(left,right)['status']=='EQUIVALENT'
    assert python_product(pair)[0]==0
    products={'dense_python_with_prepared_input':measure(lambda:python_product(pair),a.repeats),
              'python_end_to_end':measure(lambda:compare(left,right),a.repeats)}
    if a.rust_lib:
        assert rust_product(pair,a.rust_lib)==python_product(pair)
        assert compare(left,right,backend='rust',library_path=a.rust_lib)['status']=='EQUIVALENT'
        products['rust_including_ffi_conversion']=measure(lambda:rust_product(pair,a.rust_lib),a.repeats)
        products['rust_end_to_end']=measure(lambda:compare(left,right,backend='rust',library_path=a.rust_lib),a.repeats)
    result={'python':platform.python_version(),'platform':platform.platform(),'native_z3':native_version(),
            'repeats':a.repeats,'replay':replay,'product_39800_pairs':products,
            'rust_executed':bool(a.rust_lib),'scope':'Synthetic warm calls; same work per comparison. Public batch shares one receipt, individual calls have individual receipts. No MCP/startup/model latency or agent-benefit claim.'}
    text=json.dumps(result,indent=2)
    if a.output:a.output.write_text(text+'\n')
    print(text)


if __name__=='__main__':main()
