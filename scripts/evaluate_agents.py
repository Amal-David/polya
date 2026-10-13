"""Export cases, then score JSONL produced by external baseline/Polya agent runs."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from polya.evaluation import generate_cases,score_records
from polya.jsonio import loads


def main():
    p=argparse.ArgumentParser();p.add_argument('--seed',type=int,default=0)
    p.add_argument('--per-family',type=int,default=10);p.add_argument('--predictions',type=Path)
    args=p.parse_args();cases=generate_cases(args.seed,args.per_family)
    if args.predictions:
        if args.predictions.stat().st_size>10000000:raise ValueError('prediction file exceeds 10 MB')
        records=[loads(line) for line in args.predictions.read_text().splitlines() if line.strip()]
        result=score_records(cases,records)
    else:result={'cases':cases,'seed':args.seed,'conditions':['baseline','polya'],'note':'Run the same model and budgets externally; this file contains no agent results.'}
    print(json.dumps(result,ensure_ascii=True,indent=2,allow_nan=False))


if __name__=='__main__':main()
