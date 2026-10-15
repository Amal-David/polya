# Artifact-to-target plans

`mechanism.plan_scan` runs a caller-declared finite grammar of typed steps, from
a raw artifact to an exact target check. A plan can extract a PNG bit plane,
reorder it, pack bits into bytes, and test the bytes against a hash, address,
equality pattern or calibrated AES lock. The caller declares every alternative;
the operation does not infer the grammar or rank interpretations.

```bash
polya inspect mechanism.plan_inspect --example
polya inspect mechanism.plan_scan --schema
polya inspect artifact.png_bitplane
polya inspect crypto.openssl_scan
python -m examples.crypto_frontier_demo
```

The PNG path needs the `imaging` extra; see [getting started](../getting-started.md).

## A small plan

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

The same plan works through `puzzle.run` over MCP and `polya run` on the CLI.
`mechanism.recipe_scan` ([ciphers](ciphers.md)) is a separate, string-only
interface with its own resume rules.

## Types and references

Each source has an explicit kind: `png` (canonical base64 PNG file bytes),
`symbols` (Unicode code points), `bits` (ASCII 0/1) or `bytes` (strict even-length
hex). Source names and output fields are exact identifiers, not paths. A node
refers only to declared sources or earlier node outputs. All alternatives of a
node expose the same typed output ports. The candidate must be `bytes`.

| Operation | Required stream binding | Typed outputs |
| --- | --- | --- |
| `artifact.png_bitplane` | `png_base64: png` | `text: bits`, `width/height: int` |
| `grid.read` | `text: bits or symbols` | same text kind, `rows/columns: int` |
| `text.symbol_map` | `text: symbols` | `text: symbols` |
| `bits.from_symbols` | `text: symbols` | `text: bits` |
| `bits.invert` | `text: bits` | `text: bits` |
| `bits.pack` | `text: bits` | `hex: bytes` |
| `bytes.slice` | `value_hex: bytes` | `hex: bytes` |
| `grid.traverse` | `text: bits or symbols` | same text kind |
| `cipher.polyalphabetic` | `text: symbols` (optional `key: symbols`) | `text: symbols` |
| `cipher.bifid`, `cipher.checkerboard` | `text: symbols` | `text: symbols` |
| `bytes.from_radix` | `text: bits or symbols` | `hex: bytes` |
| `text.encode` | `text: symbols` | `hex: bytes` |
| `bytes.decode_text` | `value_hex: bytes` | `text: symbols` |

Grid `rows` and `columns` can be constants or integer references to PNG height
and width. A polyalphabetic key can also reference a symbols source/output. Other configuration fields are constants. A symbol map that happens
to output `0` and `1` still yields symbols until `bits.from_symbols` assigns those
meanings. There is no implicit text decoding, normalization, integer or channel
conversion, truncation or padding. `bytes.from_radix` emits exact bytes, not its optional text view. Use `bytes.decode_text` for an explicit strict codec boundary.

Preflight with `mechanism.plan_inspect`; it validates structure, not intermediate
applicability or calibration. The [agent workflow guide](../agents/agent-workflows.md)
contains a smaller `linear_plan` Python builder and complete compound examples.
No builder silently inserts conversions.

## PNG bit planes

`artifact.png_bitplane` takes canonical base64 bytes of a single-frame 8-bit PNG.
The caller picks the native channel and bit. The result keeps source and sample
hashes, dimensions and the pixel-coordinate mapping. There is no resizing,
thresholding, palette expansion, EXIF orientation or OCR. A sample index is not a
byte offset in the compressed file. Pillow's installed version is part of the
implementation fingerprint.

## Targets

A plan has one target:

- `{kind: "direct", target: ...}` uses the `crypto.target_check` contract: a SHA256
  commitment or an explicit P2PKH reading. Bitcoin and Litecoin-style version bytes
  and compressed or uncompressed SEC encodings are explicit.
- `{kind: "equality_pattern", target: ...}` uses the `pattern.equality_check`
  contract described below.
- `{kind: "openssl", lock: ...}` uses one calibrated AES lock from `crypto.openssl_scan`.

Digest, representation, pattern and pattern source are bound into the plan ID.

### Calibrated AES locks

`crypto.openssl_scan` tests a finite candidate-by-lock product. It is AES-256-CBC
with legacy `EVP_BytesToKey`, count 1, and an explicit MD5 or SHA256 digest. It is
not PBKDF2 or generalized CryptoJS Rijndael. Password modes are raw bytes,
lowercase SHA256 hex bytes and raw SHA256 bytes.

Every lock needs a known-answer calibration: ciphertext, candidate and plaintext
hash. Controls run before candidate trials, and a failed calibration produces no
candidate negatives and does not advance the cursor. Candidate IDs and sources
survive repeated byte values. Identical decryptions are reused, but each target
is checked separately.

Padding-valid bytes go straight to the declared target reading, with no language,
printability or entropy filter. Outcomes are `TARGET_MATCH`, `NO_TARGET_MATCH`,
`NO_VALID_PADDING` and `READING_NOT_APPLICABLE`. Operational failures propagate.
The scanner returns IDs and hashes, never candidate or plaintext bytes.

Limits per call: 256 candidates, eight lock/readings and 512 trials. The byte
budget charges ciphertext bytes before each uncached decryption, calibrations
included. Results give the tested half-open interval. To resume, pass `start` and
the previous `expected_plan_id`. Changing candidates, targets, conventions, sources
or the implementation invalidates that ID.

### Whole-output equality patterns

`pattern.equality_check` checks an exact byte candidate against a complete
equality relation. For every pair of positions i and j, the pattern symbols are
equal exactly when the output units are equal. One bijection covers the whole
output; matching halves, a prefix or a frequency histogram is not enough.

Target fields:

- `pattern`: 1 to 8,192 Unicode code points, kept exactly (case, whitespace,
  combining marks, non-BMP symbols). No normalization or grapheme grouping. Lone
  surrogates are rejected.
- `source`: 1 to 256 code points of caller provenance.
- `digest`: `none`, `sha256` or `sha512`, no default. The digest is applied to the
  decoded candidate bytes, not their hex text.
- `representation`: `bytes`, `hex_lower` or `hex_upper`, no default. Byte symbols
  are integers 0 to 255. Hex symbols are ASCII code points, two per byte, keeping
  leading zero nibbles.

`candidate_hex` is even-length hex without prefix or whitespace, at most 4,096
decoded bytes, either case. An empty candidate is valid input but cannot match
with `digest: "none"`. Malformed input is an error.

```python
from polya import run

result = run("pattern.equality_check", {
    "candidate_hex": "010201",
    "target": {"pattern": "雪🙂雪", "source": "planted three-position control",
               "digest": "none", "representation": "bytes"},
})["result"]
assert result["match"]
assert result["observed_partition"] == [0, 1, 0]
assert result["bijection"][0]["output_symbol"] == 1
```

A SHA256 digest has 32 byte positions or 64 hex code points; SHA512 has 64 or 128.
Every position is checked. Upper and lower hex have the same relation but distinct
output symbols and receipts.

The result keeps the target, `output_hex`, expected and observed lengths, and both
canonical partitions (block IDs from zero in first-appearance order).
`mismatch_positions` lists every overlapping position whose block IDs differ.
`missing_positions` is the pattern suffix absent from the output; `extra_positions`
is the output suffix absent from the pattern. Nothing is sampled or truncated, and
work is linear in the lengths. `TARGET_MATCH` needs equal lengths and partitions,
and its `bijection` lists every pattern symbol, output unit and first position.
`NO_TARGET_MATCH` keeps the full disagreement evidence with an empty bijection.

In a plan, both positive and negative trials keep the complete check:

```python
plan = {
    "sources": [{"id": "bytes", "kind": "bytes", "value": "010201",
                 "source": "planted exact-byte producer"}],
    "candidate": {"node": "bytes", "field": "value"},
    "target": {"kind": "equality_pattern", "target": {
        "pattern": "ABA", "source": "planted whole-output relation",
        "digest": "none", "representation": "bytes",
    }},
}
page = run("mechanism.plan_scan", {"plan": plan})["result"]
assert page["trials"][0]["target_check"]["result"]["match"]
```

## Byte and coordinate semantics

`bits.pack` consumes exactly eight bits per byte and keeps zero-valued leading
bytes. `bit_order` picks MSB-first or LSB-first within each group. An incomplete
tail is rejected unless `tail: "drop"` is set, and then the dropped bit offsets
stay in the result.

Each match carries its reference, recipe ordinal and choices, and a compact
derivation. Each step records bindings, constants, rationale, input and result
hashes, an exact coordinate map and what was lost:

- A PNG selection keeps file and sample hashes, dimensions, channel, bit and the
  row-major sample coordinate formula. Other source information is marked as not
  selected.
- A grid map records dimensions, route, reversal and the exact permutation.
- A symbol map records the mapping and dropped source offsets.
- Inversion and two-symbol interpretation keep identity offsets.
- Packing records grouping and significance order; LSB-first reverses each group.
- A byte slice records its half-open range and the omitted prefix and suffix.

Compose the maps backwards through their references to recover source coordinates.
They are exact, not sampled. Standalone conversion operations return explicit
offset arrays.

## Bounds, paging and coverage

A plan admits four sources, eight nodes, 64 alternatives per node and one million
ordered recipes. One call runs at most 512 trials and returns 16 matches. Symbols
and bits are bounded to 65,536 units; packing yields at most 8,192 bytes. Direct
targets accept 16,384 bytes. Equality-pattern and AES targets accept 4,096 candidate
bytes; select with an explicit `bytes.slice` rather than dropping bytes silently.
`text.symbol_map` keeps its 16,384-code-point limit; use `bits.from_symbols` for
full-size binary alphabets.

The plan is limited to 900,000 canonical JSON bytes, and requests and responses to
one MB. Work units charge the validated input JSON bytes on cache misses. The cache
holds eight MB in 512 entries. There is a result-size guard and a cooperative time
limit. Shared prefixes and calibrations are reused when inputs agree.

A page covers exactly `[start, stop)`. Rows separate valid negatives, matches and
invalid inputs. An unfinished trial is not included; `next_start` stays at it on
time, work, output or calibration stops. `complete` means enumeration from zero
covered the declared product. Check `coverage.invalid` and `conclusion` before
reading a negative. `NO_TARGET_MATCH_IN_COMPLETED_PLAN` requires complete
enumeration with no invalid rows.

To resume, pass the unchanged plan, `start=previous.next_start` and
`expected_plan_id=previous.plan_id`. Sources and labels, ordered alternatives,
conversions, target, calibration, implementation and runtime all feed the ID;
page budgets do not. A changed plan rejects the old ID. To record pages across
processes and recover gaps after a restart, run plans through `Ledger.run`; see
[execution](execution.md#investigation-ledger).

## The frontier demo

`examples.crypto_frontier_demo` builds three synthetic PNGs that hide binary
passwords under withheld choices of RGB channel, sample bit, traversal, polarity
and bit order. The search receives only the image, ciphertext, target and an
unrelated known control. It declares 192 programs per case, runs each case with
one `mechanism.plan_scan` call, and finds one matching candidate per case. A
wrong-target case keeps valid-padding outputs and returns no match. The PNGs come
from an independent stdlib writer and the ciphertexts from the OpenSSL CLI. The
demo also replays one published GSMG phase-2 decryption as a calibration.

### Testing candidates against the GSMG SalPhaseIon lock

The [GSMG case files](../../examples/cases/gsmg/README.md) include a profile that
runs your own candidates against the published SalPhaseIon ciphertext and target:

```bash
python -m examples.cases.gsmg.gsmg_gate --candidates candidates.json
```

`candidates.json` is a list like this (the value is an illustration, not a lead):

```json
[{"id":"experiment-17/recipe-4","value_hex":"0041ff",
  "source":"original artifact SHA256 and extraction recipe reference"}]
```

The profile checks four plaintext readings and uses SHA256 EVP as a hypothesis,
calibrated by the published phase-2 control. Another digest needs a calibration
valid for that convention. It does not cover the second 80-byte lock, Dualite,
every plaintext reduction or the planted-address route. Add separately sourced
profiles rather than merging these hypotheses. Beyond 128 candidates the profile
needs several pages; pass `start` and `expected_plan_id` through the Python API or
the JSON operation. The first 512 trials are not a complete negative.

The known public GSMG SEC key is checked against its published address, which
tests address derivation without recovering a private key. The phase-2 expected
plaintext hash was reproduced with the OpenSSL CLI. The fixture records the
upstream blob ID; no upstream oracle code is run.

## Scope and limits

- Results hold for the supplied grammar. A complete negative never refutes
  mechanisms outside it. `NO_VALID_PADDING` is a negative only for that calibrated
  cipher and password convention. `READING_NOT_APPLICABLE`, invalid inputs and
  operational failures are not negatives.
- Calibration shows the implementation matches a known convention. It does not
  show that an unknown lock uses the same convention.
- An equality-pattern match does not identify the producer; many outputs share a
  pattern. Use `crypto.target_check` when a fixed digest or address is required.
- A checksum-valid address is not proof that a puzzle is public or authorized.
  There are no transactions, network queries or private-key exports.
- Shared work and cache reuse are not independent reproduction. Empty pages and
  separate receipts do not prove exhaustion until all ranges are reconciled.
- The frontier demo is a supplied-grammar parameter search. Its cases are public
  regression data, not a held-out benchmark.
- Not implemented: learned mechanism discovery, algebraic simplification,
  dependency-safe deduction reuse, hypothesis ranking, specialist cryptanalysis
  engines, audio and video artifacts, plugin nodes, and the historical word-index
  and zero-insertion producers.
- Runtime limits are cooperative, not process isolation or a sandbox.

Sources: GSMG public constants from `floflo777/open-crypto-puzzles`,
`1-big-prizes/gsmg-io-5btc-puzzle/tools/oracle.py`, blob
`652afe0739250ef14e6c60c5f0e50987568789b7`; its README, comments and research
ledger make differing historical claims. [Frontier notes](https://github.com/floflo777/open-crypto-puzzles/blob/main/1-big-prizes/gsmg-io-5btc-puzzle/analysis/leads.md).
