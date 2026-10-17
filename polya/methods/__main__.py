"""Local JSON-only CLI; no code or source URLs are executed."""
import argparse
import json
from pathlib import Path
from .library import load_library, retrieve, read_json, read_text
from .evaluation import Budget, make_manifests, check_equal_budget, build_context, score_submission, skill_fingerprint
from .reset import digest


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    find = sub.add_parser('retrieve')
    find.add_argument('library')
    find.add_argument('query')
    find.add_argument('--limit', type=int, default=3)
    manifests = sub.add_parser('manifests')
    manifests.add_argument('library')
    manifests.add_argument('skill')
    manifests.add_argument('--model', required=True)
    manifests.add_argument('--task-id', action='append', required=True)
    manifests.add_argument('--seed', type=int, default=0)
    context = sub.add_parser('context')
    context.add_argument('task')
    context.add_argument('--arm', choices=('baseline', 'skill', 'skill_retrieval'), required=True)
    context.add_argument('--skill')
    context.add_argument('--retrieved')
    score = sub.add_parser('score')
    for key in ('task', 'gold', 'submission', 'usage'):
        score.add_argument(key)
    args = parser.parse_args()
    read = read_json
    if args.command == 'retrieve':
        result = retrieve(load_library(args.library), args.query, limit=args.limit)
    elif args.command == 'manifests':
        load_library(args.library)
        result = make_manifests(model=args.model, seed=args.seed, task_ids=args.task_id,
                                skill_hash=skill_fingerprint(args.skill),
                                library_hash=digest(read(args.library)))
        check_equal_budget(result)
    elif args.command == 'context':
        result = build_context(read(args.task), args.arm,
                               skill=read_text(args.skill) if args.skill else '',
                               retrieved=read(args.retrieved) if args.retrieved else None)
    else:
        result = score_submission(read(args.task), read(args.gold), read(args.submission),
                                  read(args.usage), Budget())
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
