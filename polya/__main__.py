"""Small JSON CLI. Inputs may come from a file or stdin to avoid quoting errors."""

# PEP 810; ignored on older Python. Keep registration and JSON semantics eager.
__lazy_modules__ = ("sqlite3",)

import argparse
import json
import sqlite3
import sys
from . import find, run
from .jsonio import loads


def main(argv=None):
    parser = argparse.ArgumentParser(prog="polya")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Report interpreter features without loading solvers")
    sub.add_parser("mcp", help="Start the local stdio MCP server")
    discover = sub.add_parser("find")
    discover.add_argument("query", nargs="?", default="")
    discover.add_argument("--limit", type=int, default=5)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("operation_id")
    execute = sub.add_parser("run")
    execute.add_argument("operation_id")
    source = execute.add_mutually_exclusive_group(required=True)
    source.add_argument("--json")
    source.add_argument("--input", help="JSON file path, or - for stdin")
    execute.add_argument("--db", help="Optional local SQLite experiment cache")
    args = parser.parse_args(argv)
    try:
        if args.command == "mcp":
            from .mcp_server import main as serve
            return serve()
        if args.command == "doctor":
            from .runtime import inspect_runtime
            result = inspect_runtime()
        elif args.command == "find":
            result = find(args.query, limit=args.limit)
        elif args.command == "inspect":
            result = find(operation_id=args.operation_id)
        else:
            if args.json is not None:
                raw = args.json
            elif args.input == "-":
                raw = sys.stdin.read(1_000_001)
            else:
                with open(args.input, encoding="utf8") as handle:
                    raw = handle.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ValueError("input JSON exceeds 1 MB")
            inputs = loads(raw)
            if args.db:
                from .session import Session
                with Session(args.db) as session:
                    result = session.run(args.operation_id, inputs)
            else:
                result = run(args.operation_id, inputs)
        print(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError, RuntimeError, sqlite3.Error) as exc:
        print(json.dumps({"execution_status": "ERROR", "error_type": type(exc).__name__,
                          "message": str(exc), "claim": "No puzzle hypothesis was rejected by this error."}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
