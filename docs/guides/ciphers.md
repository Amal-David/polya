# Ciphers and decoding recipes

These operations apply classical ciphers and decoding steps under explicit
conventions, and search finite products of complete decoding recipes. They do
not infer an author's mechanism: a tool that applies Bifid with a supplied
square does not discover the square.

## Operations

| Need | Operation |
| --- | --- |
| Read a transcribed symbol grid from any corner, in either spiral direction | `grid.traverse` |
| Map symbols to digits or other symbols and keep a record of deletions | `text.symbol_map` |
| Tell grouped digits apart from one whole decimal, binary or hex integer | `bytes.from_radix` |
| Apply Vigenere, Beaufort or variant Beaufort under an exact alphabet | `cipher.polyalphabetic` |
| Apply Bifid with a given square, period and direction | `cipher.bifid` |
| Read a caller-supplied prefix-free straddling checkerboard | `cipher.checkerboard` |
| Recover constrained key slots, or contradict periodic-key hypotheses, from cribs | `cipher.periodic_cribs` |
| Search a finite product of complete decoding recipes | `mechanism.recipe_scan` |
| Re-encrypt and check a periodic-cipher proposal from an external engine | `specialist.verify_proposal` |

Lower-level crypto operations are `crypto.openssl_inspect`, `crypto.openssl_decrypt`,
`crypto.bip39_seed`, `verify.sha256` and `evidence.padding_null`. All contracts are in
the [operation reference](../operations.md).

```bash
polya find "periodic key crib"
polya inspect mechanism.recipe_scan
polya inspect cipher.periodic_cribs
python -m examples.cryptic_demo
```

## Recipe search

`mechanism.recipe_scan` takes up to six stages. Each stage lists explicit
alternatives, and the operation enumerates their product in a stable order.
The caller gives a rationale for each alternative and a checkpoint. A checkpoint
tests a prefix, the exact text, or the SHA-256 of the UTF-8 output. A step looks
like this:

```python
{
    "operation_id": "cipher.bifid",
    "input_field": "text",
    "inputs": {"square": "ABCDEFGHIKLMNOPQRSTUVWXYZ", "period": 7},
    "output_field": "text",
    "rationale": "The clue suggests fractionation; period 7 is a hypothesis."
}
```

Every selected output must be a bounded string. Source text is not normalized.
Shared subcomputations are reused within one call; distinct recipes and duplicate
derivations stay separate. Rejected branches do not return their intermediate
strings. Matches keep their output and step trace. The trace reports dropped
characters and leftover digits where relevant. It is not a full source-dependency
proof. Besides the cipher and text operations, the recipe allowlist admits
`bytes.decode` and `crypto.openssl_decrypt` under their own contracts.

Status and paging:

- `complete` is true only when enumeration ran from ordinal zero through the whole
  declared product. Finishing a later suffix sets `range_exhausted` instead.
- Time, work, match and trial limits return the next uncompleted ordinal.
- A recipe whose input fails validation is kept as `INVALID_RECIPE_INPUT`. A kernel
  that breaks its output contract raises an operational error.

Limits: one million declared recipes, 512 attempted per call, 16 matches and
16,384-codepoint intermediates, plus separate work, time, definition-size, output
and internal-cache limits. Deadlines are cooperative. Pruning uses only execution
applicability and the checkpoint. There is no learned generator, beam search,
probabilistic ranking or automatic cipher-family identification.

## Cribs as constraints

A crib is a known plaintext fragment at a known offset. For each proposed period,
`cipher.periodic_cribs` derives the required key-slot values. A conflict reports
both positions and their source labels. The result gives the exact number of
remaining keys for the model without enumerating them. Partly determined keys
contain null slots; they are not filled in with guessed words.

The conventions are modular arithmetic over the caller's ordered alphabet:

- Vigenere: ciphertext = plaintext + key.
- Variant Beaufort: ciphertext = plaintext - key.
- Beaufort: ciphertext = key - plaintext.

There is no case folding, alphabet repair or I/J merging. Repeating-key
constraints do not cover autokey, transpositions, unknown alignments or AES.
A contradiction refutes only that family, alphabet, crib set and period.

## Verifying external proposals

`specialist.verify_proposal` checks a key proposed by an external solver by
re-encrypting under the supplied conventions, without calling that solver. It
covers periodic Vigenere and Beaufort only. Status is exactly one of `REJECTED`,
`CHECKPOINT_MATCH` or `MECHANISM_CONSISTENT_ONLY`. Every result keeps the supplied
`expected_plaintext_sha256` and `checkpoint_source`, both `null` when no checkpoint
is given.

`artifact_sha256` hashes the exact ciphertext string. `plaintext_sha256` and
`expected_plaintext_sha256` hash the exact plaintext string. All three use UTF-8
without normalization or a byte-order mark, reported as `digest_encoding: "utf-8"`.
They are not digests of original artifact files, other encodings, or JSON.

## Historical checkpoint replay

`examples.cryptic_demo` replays four published checkpoints from two public
puzzles. The fixture and its provenance (commit and blob IDs, representation
changes) are in [examples/cases/gsmg](../../examples/cases/gsmg/README.md).

1. GSMG's published 14x14 matrix: 8 corner and direction choices x 2 polarities
   x 2 bit orders = 32 recipes. The checkpoint is the known challenge hostname,
   not the full answer. One recipe recovers the published path. The final four
   bits are reported as `0000`, not discarded. The input is a public binary
   transcription, not the original image.
2. Two published SalPhaseIon number strings: an explicit character-to-digit map
   followed by whole-integer decimal decoding reproduces their published texts.
3. Kryptos K1: with the known keyed alphabet and a ten-character plaintext prefix
   supplied after the fact, the period-10 key is determined, and it reproduces
   the unused suffix. Choosing the right family and period was not autonomous.
   K4 is not attempted.

Tests also compare cribs with exhaustive key enumeration, Bifid with a separate
coordinate-string implementation, and spiral traversal with independent boundary
peeling. Invalid inputs, partial work, output-contract failures and cursors have
regression checks.

Some operations carry a `gsmg` discovery keyword because they apply to documented
GSMG stages. The algorithms contain no puzzle constants.

## Scope and limits

- A checkpoint is a filter, not an authenticated oracle. Do not use padding as a
  final checkpoint or treat a readable substring as independent confirmation.
- Keep positive calibration controls separate from a real unknown candidate. A
  result picked after reading its answer is not held out.
- The checkpoint replays are not new solutions or blinded agent evaluations.
  Source labels and fixture provenance are not cryptographic authentication.
- No GPU brute force, network service, wallet transaction or code chosen by an
  executable string is involved.
- See [scope](../internals/scope.md) for priorities, including specialist
  cryptanalysis adapters such as [Colossus](https://github.com/stblake/colossus),
  and [execution](execution.md#evaluation) for how to measure usefulness.

Sources: [GSMG community transcriptions](https://github.com/puzzlehunt/gsmgio-5btc-puzzle/blob/fb92dd15487c6e2d275adb8c923698b7166c328e/README.md);
[K1 ciphertext](https://github.com/stblake/colossus/blob/main/ciphers/kryptos/K1.txt)
(blob `f3a9f22168082933208369a865adf83dd5818db4`);
[PuzzleWorld](https://arxiv.org/abs/2506.06211) on open-ended mechanism discovery
versus well-specified tasks.
