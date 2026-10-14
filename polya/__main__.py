"""Small JSON CLI. Inputs may come from a file or stdin to avoid quoting errors."""

# PEP 810; ignored on older Python. Keep registration and JSON semantics eager.
__lazy_modules__ = ("sqlite3",)

import argparse
from itertools import groupby
import json
import sqlite3
import sys
from . import find, list_operations, run
from .jsonio import loads

_UNIONS = ("anyOf", "oneOf", "allOf")
_KEYWORDS = ("minLength", "maxLength", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
             "multipleOf", "pattern", "minItems", "maxItems", "minProperties", "maxProperties")


def _type(schema):
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    for union in _UNIONS:
        if union in schema:
            return " | ".join(_type(option) for option in schema[union])
    kind = schema.get("type", "any")
    nested = schema.get("items") if kind == "array" else schema.get("additionalProperties") if kind == "object" else None
    if isinstance(nested, dict):
        item = _type(nested)
        return f"{kind} of ({item})" if " | " in item else f"{kind} of {item}"
    return kind if type(kind) is str else " | ".join(kind)


def _constraints(schema):
    parts = [f"{key} {schema[key]}" for key in _KEYWORDS if key in schema]
    if "enum" in schema:
        parts.append("enum: " + ", ".join(value if type(value) is str else json.dumps(value) for value in schema["enum"]))
    if "const" in schema:
        parts.append(f"const: {schema['const']}")
    for union in _UNIONS:
        for option in schema.get(union, ()):
            parts += _constraints(option)
    if isinstance(schema.get("items"), dict):
        parts += ["items " + part for part in _constraints(schema["items"])]
    return parts


def _entry(schema, required=None):
    entry = {"type": _type(schema)}
    if required is not None:
        entry["required"] = required
    if "default" in schema:
        entry["default"] = schema["default"]
    constraints = _constraints(schema)
    if constraints:
        entry["constraints"] = "; ".join(constraints)
    if "description" in schema:
        entry["description"] = schema["description"]
    return entry


def _fields(schema):
    required = set(schema.get("required", ()))
    return {name: _entry(prop, name in required) for name, prop in schema.get("properties", {}).items()}


def _compact(contract):
    # pydantic emits $defs only for models the input schema references.
    inputs = contract["input_schema"]
    return {**{key: contract[key] for key in ("operation_id", "version", "title", "description", "postcondition", "limits")},
            "cacheable": contract["cache_policy"] == "exact_request", "inputs": _fields(inputs),
            "definitions": {name: _fields(schema) if "properties" in schema else _entry(schema)
                            for name, schema in inputs.get("$defs", {}).items()},
            "outputs": {name: _type(prop) for name, prop in contract["output_schema"].get("properties", {}).items()},
            "example": contract["example"]}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="polya", description="Discover, inspect and run deterministic puzzle operations.")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.add_parser("doctor", help="Report interpreter features without loading solvers")
    sub.add_parser("mcp", help="Start the local stdio MCP server")
    listing = sub.add_parser("list", help="List every operation grouped by family")
    listing.add_argument("--family", help="Show only one family, such as cipher or bytes")
    listing.add_argument("--json", action="store_true", help="Print the list as JSON instead of text")
    discover = sub.add_parser("find", help="Search operations by keywords")
    discover.add_argument("query", nargs="?", default="", help="Keywords matched against operation IDs, titles and terms")
    discover.add_argument("--limit", type=int, default=5, help="Maximum number of results, from 1 to 100")
    inspect = sub.add_parser("inspect", help="Show one operation's inputs, outputs and example")
    inspect.add_argument("operation_id", help="Operation to describe, such as cipher.polyalphabetic")
    view = inspect.add_mutually_exclusive_group()
    view.add_argument("--schema", action="store_true", help="Print the full contract with JSON schemas")
    view.add_argument("--example", action="store_true", help="Print only the example inputs, ready for run --input -")
    execute = sub.add_parser("run", help="Run one operation on JSON inputs")
    execute.add_argument("operation_id", help="Operation to run, such as bytes.decode")
    source = execute.add_mutually_exclusive_group(required=True)
    source.add_argument("--json", help="Inputs as an inline JSON object")
    source.add_argument("--input", help="JSON file path, or - for stdin")
    execute.add_argument("--db", help="Optional local SQLite experiment cache")
    execute.add_argument("--result-only", action="store_true", help="Print only the result object, without the receipt")
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        if args.command == "mcp":
            from .mcp_server import main as serve
            return serve()
        if args.command == "doctor":
            from .runtime import inspect_runtime
            result = inspect_runtime()
        elif args.command == "list":
            def family(row):
                return row["operation_id"].partition(".")[0]
            result = list_operations()
            if args.family is not None:
                matching = [row for row in result if family(row) == args.family]
                if not matching:
                    raise ValueError(f"unknown family {args.family!r}; families: {', '.join(dict.fromkeys(map(family, result)))}")
                result = matching
            if not args.json:
                for name, rows in groupby(result, key=family):
                    print(name)
                    for row in rows:
                        print(f"  {row['operation_id']}  {row['title']}")
                return 0
        elif args.command == "find":
            result = find(args.query, limit=args.limit)
            if not result:
                print(f"No operations matched {args.query!r}. Run 'polya list' to see all {len(list_operations())} operations.",
                      file=sys.stderr)
        elif args.command == "inspect":
            result = find(operation_id=args.operation_id)
            if args.example:
                if result["example"] is None:
                    raise ValueError(f"{args.operation_id} has no example; run 'polya inspect {args.operation_id}' to see its inputs.")
                result = result["example"]
            elif not args.schema:
                result = _compact(result)
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
            if args.result_only:
                result = result["result"]
        print(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError, RuntimeError, sqlite3.Error) as exc:
        print(json.dumps({"execution_status": "ERROR", "error_type": type(exc).__name__,
                          "message": str(exc), "claim": "No puzzle hypothesis was rejected by this error."}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
