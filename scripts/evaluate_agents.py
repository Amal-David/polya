"""Export cases, then score JSONL produced by external baseline/Polya agent runs."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from polya.evaluation import generate_cases,score_records
from polya.jsonio import loads
from scripts.agent_benchmark import protocol, score, self_check


def read_bounded(path, limit):
    with path.open('rb') as source:
        raw=source.read(limit+1)
    if len(raw)>limit:raise ValueError(f'file exceeds {limit} bytes')
    return raw.decode('utf8')


def read_records(path, max_records):
    records=[]
    for line in read_bounded(path,10000000).splitlines():
        if not line.strip():continue
        if len(records)>=max_records:raise ValueError('too many prediction records')
        records.append(loads(line))
    return records


def main():
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,default=0)
    p.add_argument('--per-family',type=int,default=10);p.add_argument('--predictions',type=Path)
    p.add_argument('--roadmap',action='store_true',help='Use the three-condition held-out protocol')
    p.add_argument('--manifest',type=Path,help='Score or self-check the exact saved roadmap protocol')
    p.add_argument('--split',choices=['development','heldout'],default='heldout')
    p.add_argument('--model-id',default='unrun')
    p.add_argument('--tokens',type=int,default=8000)
    p.add_argument('--tool-calls',type=int,default=40)
    p.add_argument('--wall-ms',type=int,default=120000)
    p.add_argument('--self-check',action='store_true',help='Synthetic oracle/scorer check, not agent evidence')
    args=p.parse_args()
    if args.roadmap:
        if args.manifest:
            if not (args.predictions or args.self_check): p.error('--manifest requires scoring or --self-check')
            manifest=loads(read_bounded(args.manifest,2000000))
        else:
            manifest=protocol(args.split,args.per_family,{'tokens':args.tokens,'tool_calls':args.tool_calls,'wall_ms':args.wall_ms})
        if args.self_check:
            if args.predictions: p.error('--self-check cannot score --predictions')
            result=self_check(manifest)
        elif args.predictions:
            records=read_records(args.predictions,600)
            result=score(manifest,records,args.model_id)
        else: result=manifest
        print(json.dumps(result,ensure_ascii=True,indent=2,allow_nan=False))
        return
    if args.self_check or args.manifest: p.error('--self-check and --manifest require --roadmap')
    cases=generate_cases(args.seed,args.per_family)
    if args.predictions:
        records=read_records(args.predictions,1200)
        result=score_records(cases,records)
    else:result={'cases':cases,'seed':args.seed,'conditions':['baseline','polya'],'note':'Run the same model and budgets externally; this file contains no agent results.'}
    print(json.dumps(result,ensure_ascii=True,indent=2,allow_nan=False))


if __name__=='__main__':main()
