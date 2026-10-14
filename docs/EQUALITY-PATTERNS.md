# Whole-output equality-pattern targets (unreleased)

`pattern.equality_check` checks a caller-supplied exact byte candidate against a
complete equality relation. It never generates a candidate or chooses a producer.
For every pair of positions i and j, the pattern symbols must be equal if and only
if the output units are equal. One shared bijection covers the entire output.
Matching separate halves, a prefix or a frequency histogram is insufficient.

## Explicit conventions

The required target fields are:

- `pattern`: 1–8,192 Unicode codepoints. Case, whitespace, combining marks and
  non-BMP symbols are retained exactly. There is no Unicode normalization,
  grapheme grouping or ignored symbol. Lone surrogates are rejected.
- `source`: caller-supplied provenance, 1–256 codepoints. It is not authenticated.
- `digest`: `none`, `sha256` or `sha512`, with no default. The digest receives the
  exact decoded candidate bytes, never their hex text. `none` retains those bytes.
- `representation`: `bytes`, `hex_lower` or `hex_upper`, with no default. Byte
  symbols are integers 0–255 with no text decoding. Hex symbols are individual
  ASCII codepoints, two per byte, preserving leading zero nibbles and all bytes.

`candidate_hex` is even-length hex with no prefix or whitespace, at most 4,096
decoded bytes. Either input hex case is accepted without changing its bytes.
An empty candidate is admitted, but cannot match the required nonempty pattern
when `digest: "none"`. Malformed input is an error, not a negative result.

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

For a full 64-position hex-digest consumer, declare `digest: "sha256"`, a hex
representation and all 64 pattern symbols. Every position is checked. SHA256
byte representation has 32 positions; SHA512 has 64 bytes or 128 hex codepoints.
No algorithm, output length, slice, alphabet mapping or normalization is guessed.
Hex upper/lower representations have the same equality relation, but their exact
chosen output symbols, convention and receipts remain distinct.

## Full evidence and its limits

The result retains the target, output bytes as `output_hex`, expected/observed
lengths and complete canonical partitions. Canonical block IDs start at zero
in first-appearance order. `mismatch_positions` lists every position in the
overlapping length whose canonical block IDs differ. These are vector
differences, not a claim that each position independently caused a conflict.
`missing_positions` lists the pattern suffix absent from the output;
`extra_positions` lists the output suffix absent from the pattern. No evidence is
sampled or truncated. The representation reconstructs exact observed units from
`output_hex`. Work is linear in the admitted lengths, without a quadratic list
of all position pairs.

`TARGET_MATCH` requires equal whole lengths and equal whole partitions. Its
`bijection` lists every pattern symbol, mapped output unit and first position.
`NO_TARGET_MATCH` retains full disagreement evidence and an empty bijection.
One candidate can be checked through Python, CLI or `puzzle.run` on MCP using
the same operation.

This is an equality-relation test, not an exact digest-value test. Many possible
outputs may have the same pattern, especially when all symbols are distinct.
Use existing `crypto.target_check` when a fixed digest or address is required.
A match does not identify the intended source-to-answer producer or establish
a puzzle solution. No new solved target, speedup or cryptanalytic capability is
claimed. Candidate hashes/receipts provide consistency, not authentication.

## Typed plans and history

Use the same target in a plan:

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

Both positive and negative valid trials retain the complete target check.
Existing work, time and output budgets apply. An interrupted trial keeps the
same cursor; oversized candidates are invalid recipes and do not establish a
negative. Pattern, source, digest and representation changes reject a stale
resume ID. `Ledger.run` and `plan_coverage` retain their existing semantics;
preserve the returned envelope for full evidence because the ledger stores
compact outcome/hash links rather than original artifacts or target vectors.

This feature does not add the historical word-index or zero-insertion producers.
The existing `encoding.radix_bytes` operation is unchanged and is not newly
admitted as a typed-plan node. Those are independent producer-interface changes.
