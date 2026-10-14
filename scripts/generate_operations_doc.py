"""Write docs/operations.md from the operation registry.

Run ``python scripts/generate_operations_doc.py`` after changing an operation.
``--check`` exits 1 when the committed file differs from the registry.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUTPUT = ROOT / "docs" / "operations.md"

from polya.catalog import REGISTRY  # noqa: E402


def type_name(schema: dict) -> str:
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    if "anyOf" in schema or "oneOf" in schema:
        return " or ".join(type_name(part) for part in schema.get("anyOf", schema.get("oneOf")))
    if "enum" in schema:
        return "one of " + ", ".join(f"`{json.dumps(value, ensure_ascii=False)}`" for value in schema["enum"])
    if "const" in schema:
        return f"`{json.dumps(schema['const'], ensure_ascii=False)}`"
    kind = schema.get("type")
    if isinstance(kind, list):
        return " or ".join(kind)
    if kind == "array":
        if "prefixItems" in schema:
            return "tuple of " + ", ".join(type_name(item) for item in schema["prefixItems"])
        return f"array of {type_name(schema['items'])}" if schema.get("items") else "array"
    if kind == "object" and isinstance(schema.get("additionalProperties"), dict):
        return f"object of {type_name(schema['additionalProperties'])}"
    return kind or "any"


def field_line(name: str, schema: dict, required: bool) -> str:
    line = f"- `{name}`: {type_name(schema)}"
    if not required and "default" in schema:
        default = json.dumps(schema["default"], ensure_ascii=False)
        if len(default) <= 60:
            line += f", default `{default}`"
    if schema.get("description"):
        line += f". {schema['description']}"
    return line


def limit_items(limits) -> list[str]:
    if isinstance(limits, dict):
        return [f"{key}: {value}" for key, value in limits.items()]
    if isinstance(limits, (list, tuple)):
        return [str(item) for item in limits]
    return [part.strip() for part in str(limits).split(";") if part.strip()]


def operation_section(operation) -> list[str]:
    contract = operation.contract()
    lines = [f"### `{operation.operation_id}`", "", f"**{operation.title}.** "
             f"Version {operation.version}; cacheable: {'yes' if operation.cacheable else 'no'}.", ""]
    if operation.description != operation.title:
        lines += [operation.description, ""]
    lines += [f"Postcondition: {operation.postcondition}", "", "Limits:", ""]
    lines += [f"- {item}" for item in limit_items(operation.limits)] + [""]
    inputs = contract["input_schema"]
    properties = inputs.get("properties", {})
    required = set(inputs.get("required", []))
    for label, wanted in (("Required inputs", True), ("Optional inputs", False)):
        names = [name for name in properties if (name in required) == wanted]
        if names:
            lines += [f"{label}:", ""]
            lines += [field_line(name, properties[name], wanted) for name in names] + [""]
    outputs = list(contract["output_schema"].get("properties", {}))
    lines += ["Output fields: " + ", ".join(f"`{name}`" for name in outputs) + ".", ""]
    example = getattr(operation, "example", None)
    if isinstance(example, dict):
        lines += ["Example input:", "", "```json", json.dumps(example, indent=2, ensure_ascii=False), "```", ""]
    return lines


def generate() -> str:
    families: dict[str, list] = {}
    for operation_id in sorted(REGISTRY):
        families.setdefault(operation_id.split(".", 1)[0], []).append(REGISTRY[operation_id])
    lines = ["# Operation reference", "",
             f"Polya registers {len(REGISTRY)} operations in {len(families)} families. "
             "This file is generated from `polya.catalog.REGISTRY` by "
             "`scripts/generate_operations_doc.py`; do not edit it by hand. "
             "Run `polya inspect ID --schema` for the full JSON schema of one operation.", "",
             "Families: " + ", ".join(f"[{name}](#{name})" for name in families) + ".", ""]
    for family, operations in families.items():
        lines += [f"## {family}", ""]
        for operation in operations:
            lines += operation_section(operation)
    return "\n".join(lines).rstrip("\n") + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the committed file is stale")
    args = parser.parse_args()
    text = generate()
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else None
        if current != text:
            print(f"{OUTPUT.relative_to(ROOT)} is out of date; run python scripts/generate_operations_doc.py",
                  file=sys.stderr)
            return 1
        return 0
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
