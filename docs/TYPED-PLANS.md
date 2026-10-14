# Typed artifact-to-target investigations (unreleased)

`mechanism.plan_scan` executes a caller-declared finite grammar through typed
references. It does not infer the grammar, rank interpretations, execute arbitrary
code, browse files/URLs, or discover a puzzle solution. Existing `mechanism.scan`
and all primitive operations remain compatible. The new endpoint, including its
resume rules, is distinct from that legacy string-only recipe interface.

## A small complete plan

```python
from polya import run

plan = {
    "sources": [{"id": "evidence", "kind": "bits", "value": "0000000001000001",
                 "source": "a supplied two-byte bit stream"}],
    "nodes": [{"id": "packed", "alternatives": [{
        "operation_id": "bits.pack",
        "bindings": {"text": {"node": "evidence", "field": "value"}},
        "inputs": {"bit_order": "msb", "tail": "reject"},
        "rationale": "two complete eight-bit groups, retaining the leading zero",
    }]}],
    "candidate": {"node": "packed", "field": "hex"},
    "target": {"kind": "direct", "target": {
        "kind": "sha256",
        "value": "c00b4d3c929cb5cc316691ed4636f634576f2c9b2954767234c5274e9dde185d",
        "source": "SHA256 of the independent byte fixture 0041",
    }},
}
page = run("mechanism.plan_scan", {"plan": plan})
assert page["result"]["matches"][0]["candidate_hex"] == "0041"
```

Use `polya inspect mechanism.plan_scan` for the authoritative JSON schema. The
same plan works through `puzzle.run` on MCP and `polya run` on the CLI. The
[frontier demo](../examples/crypto_frontier_demo.py) declares 192 PNG-to-AES
recipes and executes them with one operation call per fixture; it no longer
contains bespoke candidate-extraction/search loops. Its Python comprehensions
only construct the finite alternatives that an agent can supply as JSON.

## Types and references

Sources have an explicit kind: `png` (canonical base64 PNG file bytes), `symbols`
(Unicode codepoints), `bits` (ASCII 0/1), or `bytes` (strict even-length hex).
Source names and output fields are exact identifiers, never executable paths.
A node refers only to declared sources or earlier node outputs. Alternatives
must expose the same typed output ports. Candidate output must be `bytes`.

The initial bounded vocabulary is intentionally small:

| Operation | Required stream binding | Typed outputs |
| --- | --- | --- |
| `artifact.png_bitplane` | `png_base64: png` | `text: bits`, `width/height: int` |
| `grid.read` | `text: bits or symbols` | same text kind, `rows/columns: int` |
| `encoding.symbol_map` | `text: symbols` | `text: symbols` |
| `symbols.to_bits` | `text: symbols` | `text: bits` |
| `bits.invert` | `text: bits` | `text: bits` |
| `bits.pack` | `text: bits` | `hex: bytes` |
| `bytes.slice` | `value_hex: bytes` | `hex: bytes` |

Grid rows/columns can be explicit constants or integer references to PNG
height/width. No other constant fields accept references. A symbol mapping that
happens to produce `0` and `1` is still symbols until `symbols.to_bits` explicitly
assigns those meanings. There is no implicit text decode, normalization, integer
conversion, channel conversion, truncation or padding.

The target is either `{kind: "direct", target: ...}` using the existing exact
SHA256/P2PKH target contract, or `{kind: "openssl", lock: ...}` using one existing
calibrated AES lock contract. `NO_VALID_PADDING` is a negative only for that
specified calibrated cipher/password convention. `READING_NOT_APPLICABLE`,
invalid recipe inputs and operational failures are not target negatives.
OpenSSL calibration failure stops without advancing that candidate's cursor.

## Exact byte and coordinate semantics

`bits.pack` consumes exactly eight bits per byte. It preserves zero-valued
leading bytes and all 256 byte values, without interpreting bytes as text.
`bit_order` explicitly chooses MSB-first or LSB-first significance within each
group. An incomplete tail is rejected unless `tail: "drop"` explicitly permits
it; the exact dropped bit offsets remain in the result and derivation.

Each matched candidate carries its reference, recipe ordinal/choices and full
compact derivation. Each step records bindings, constants, rationale, validated
input/result hashes, an exact coordinate map and loss semantics:

- A PNG selection retains file/sample hashes, dimensions, native channel, bit,
  and the row-major sample coordinate formula. It selects one bit of one native
  sample channel; other source information is explicitly not selected.
- A grid map records dimensions, route and reversal, an exact permutation.
- Symbol expansion records the explicit mapping and dropped source offsets.
- Inversion and two-symbol interpretation retain identity offsets.
- Packing records fixed-width grouping and significance order; LSB-first reverses
  each group's significance offsets.
- A byte slice records its half-open range and exact omitted prefix/suffix ranges.

Compose these maps backwards through their named references to recover source
coordinates. They are compact exact maps, not sampled/truncated offset lists.
PNG sample coordinates are not byte offsets in the compressed PNG file. Source
labels are caller assertions, and hashes/derivations are not authentication or
proof of the intended interpretation. Standalone conversion operations also
return explicit offset arrays.

## Bounds, paging and coverage

Plans admit four sources, eight nodes, 64 alternatives per node, and at most one
million ordered recipes. One call admits 512 trials and 16 matches. Symbols and
bits are bounded to 65,536 units throughout the new PNG/grid/binary route;
packing yields at most 8,192 bytes. Direct target checks accept up to 16,384
bytes. The existing calibrated scanner accepts at most 4,096 candidate bytes:
use an explicit `bytes.slice` when the proposed interpretation requires selection,
or keep the full bytes for a direct target. Never silently drop an oversized
password. Existing `encoding.radix_bytes` limits are unchanged. The optional
`encoding.symbol_map` node also retains its existing 16,384-codepoint limit;
use the new explicit two-symbol conversion for full-size binary alphabets.

The plan itself is limited to 900,000 canonical JSON bytes; the public operation
retains its one-MB request/response admission checks. Work units charge the full
validated input JSON bytes on cache misses. There is an eight-MB serialized cache
budget, 512 cache entries, a result-size guard, and a cooperative time limit.
These are bounded orchestration limits, not CPU quotas, process isolation or a
security sandbox. Shared prefixes/calibrations are reused where inputs agree;
reuse does not constitute independent reproduction.

A returned page covers exactly `[start, stop)`. Its rows distinguish valid
negatives, matches and invalid/unapplicable inputs. An unfinished trial is not
included, and `next_start` remains at that ordinal on time, work, output or
calibration stops. `complete` means enumeration from zero exhausted the declared
product; inspect `coverage.invalid` and `conclusion` before drawing a negative.
`NO_TARGET_MATCH_IN_COMPLETED_PLAN` requires complete enumeration with no invalid
rows. It never refutes mechanisms outside this grammar.

Resume with the unchanged plan, `start=previous.next_start`, and
`expected_plan_id=previous.plan_id`. Source content/labels, ordered alternatives,
conversions, target/calibration and implementation/runtime all contribute to
identity. Page budgets do not. A changed plan rejects the old ID. An exhausted
suffix never claims an untested prefix was covered. Empty pages and separate
page receipts do not prove global exhaustion without reconciling all ranges.

## Opt-in execution-backed history

```python
from polya.ledger import Ledger

with Ledger("investigation.sqlite") as log:
    first = log.run("mechanism.plan_scan", {"plan": plan, "max_trials": 1})
    plan_id = first["result"]["plan_id"]

# A different process/agent can reopen the same explicitly selected database.
with Ledger("investigation.sqlite") as log:
    history = log.plan_coverage(plan_id)
    print(history["gaps"], history["unresolved_ranges"], history["pages"])
```

`Ledger.run` executes the operation itself, validates receipt/request/result and
plan linkage, and atomically appends a compact execution record. It returns the
ordinary envelope plus `ledger_event_id`. Generic `append` claims do not become
execution coverage. Counts come from terminal ordinal/outcome rows, not supplied
coverage counters. Arbitrary external receipts cannot be imported through this
interface. It stores receipt/hash links and compact outcomes, not full plans,
source bytes or candidate bytes: preserve the original plan and returned envelope
separately when reproduction is needed.

`plan_coverage` reports actual recorded ranges, unique counts, unvisited gaps,
unresolved invalid inputs, overlaps, conflicting outcomes, receipt/event links,
and excluded retracted/dependency-invalid pages. Reopening a ledger does not
re-execute prior work or carry coverage across a different plan ID. Overlap is
not corroboration. Unknown plans have no inferred total. A process killed before
an atomic record finishes leaves no claimed page; retrying may duplicate work
but cannot turn an interrupted trial into a negative.

This remains an explicitly local Python history API, not an MCP filesystem or
network capability. Existing generic events and retraction propagation remain
available. Hash checks detect inconsistent edits, not a party who can rewrite
all database records; no authentication or independent-reproduction claim is made.

## Deliberately deferred

This slice does not add learned mechanism discovery, algebraic simplification,
dependency-safe symbolic deduction reuse, new hypothesis-ranking/discriminating
experiment algorithms, specialist cryptanalysis engines, generalized audio/video
artifacts, arbitrary plugin nodes, or automatic investigation strategy. The
existing symbolic/automata APIs remain available separately. Three supplied-
grammar fixture recoveries are integration evidence, not an evaluated LLM gain
or a newly solved open puzzle.
