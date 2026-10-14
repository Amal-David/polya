# Cryptographic puzzles: useful moves before formal solving

Polya's core is reusable, but development should be driven by real public-puzzle
work. An arrangement solver does not infer an author's decoding mechanism. Fast
state-machine traversal does not make an unknown AES password less unknown.

## Implemented in this change

| Need | Operation |
| --- | --- |
| Read a transcribed symbol grid from different corners and in either spiral direction | `grid.traverse` |
| Try explicit symbol-to-digit mappings and preserve deletions | `encoding.symbol_map` |
| Distinguish grouped digits from a whole decimal/binary/hex integer | `encoding.radix_bytes` |
| Apply Vigenere, Beaufort or variant Beaufort under an exact alphabet | `cipher.polyalphabetic` |
| Apply Bifid under a specified square, period and direction | `cipher.bifid` |
| Read a caller-supplied prefix-free straddling checkerboard | `cipher.checkerboard` |
| Recover constrained key slots or contradict periodic-key hypotheses from cribs | `cipher.periodic_cribs` |
| Compare a finite product of complete decoding recipes without rewriting their common prefixes | `mechanism.scan` |

The facade is `polya`; the existing implementation namespace is `puzzleops`.
All eight operations use the existing contracts, receipts, CLI and MCP tools.
No network service, wallet transaction, arbitrary code, or cipher backend chosen
by executable strings has been added. Other runtime/worker/Rust APIs are unchanged.

```bash
python -m polya find gsmg
python -m polya inspect mechanism.scan
python -m polya inspect cipher.periodic_cribs
python -m examples.cryptic_demo
```

The GSMG discovery keyword identifies operations useful on its documented stages;
it is not a claim that they solve the final gate. The algorithms have no puzzle
constants. Historical fixtures live separately in `examples/data/`.

## Search mechanisms, not only guessed answers

`mechanism.scan` accepts up to six stages, each containing explicit alternatives.
It enumerates the product in stable order. The agent supplies a rationale for each
alternative and an external checkpoint. It can test a prefix, exact text or the
SHA-256 of the UTF-8 output. A checkpoint is a filter, not an authenticated oracle.

A step contains:

```python
{
    "operation_id": "cipher.bifid",
    "input_field": "text",
    "inputs": {"square": "ABCDEFGHIKLMNOPQRSTUVWXYZ", "period": 7},
    "output_field": "text",
    "rationale": "The supplied clue suggests fractionation; period 7 is a hypothesis."
}
```

Every selected output must be a bounded string. No source normalization is
implicit. Shared subcomputations are reused within the call, while distinct
recipes and duplicate derivations remain separate. Intermediate strings are
not dumped into the agent's context for every rejected branch. Matches retain
output and step trace. The trace reports dropped-character counts and leftover
digits where relevant; it is NOT a full source-dependency proof.

The recipe allowlist also admits existing `bytes.decode` and
`crypto.openssl.decrypt` operations, under their original explicit contracts.
Do not use padding as a final checkpoint or treat an arbitrary readable substring
as independent confirmation. This layer does not add GPU brute force.

### Boundaries and reproducibility

- `complete` is true only for enumeration from ordinal zero through the entire
  declared recipe product. An exhausted suffix sets `range_exhausted`, not global
  completion. Time/work/match/trial limits retain the next uncompleted ordinal.
- A recipe input failure is retained as `INVALID_RECIPE_INPUT`, never silently
  promoted to evidence that the puzzle hypothesis is impossible. A kernel that
  violates its output contract raises an operational error.
- The maximum is one million declared recipes, 512 attempted per call, 16
  matches, and 16,384-codepoint intermediates. There are separate work, time,
  definition-size, output and internal-cache limits. Deadlines are cooperative.
- Search pruning is limited to execution applicability and the caller checkpoint.
  There is no learned hypothesis generator, beam search, probabilistic ranking,
  automatic cipher-family identification or autonomous discovery in this release.
- Keep positive calibration controls separate from a real unknown candidate.
  Don't select the best result after reading its answer and then call it held out.

## Cribs as constraints, rather than language-model guesses

A crib is a supplied plaintext fragment at a known offset. For each proposed
period, `cipher.periodic_cribs` derives required key-slot values. Conflicts include
the two positions and their source labels. It returns exact remaining-key counts
for this model without enumerating all keys. Partially determined keys contain
null slots; they are not silently completed using English word guesses.

The models use explicit modular conventions:

- Vigenere: ciphertext = plaintext + key.
- Variant Beaufort: ciphertext = plaintext - key.
- Beaufort: ciphertext = key - plaintext.

Arithmetic is modulo the size of the caller's ordered alphabet. No automatic
case folding, alphabet repair or I/J merging occurs. Repeating-key constraints do
not apply automatically to autokey, transpositions, unknown alignments or AES.
A contradiction refutes only the specific family/alphabet/crib/period combination.

## Historical checkpoint suite

`examples.cryptic_demo` executes four calibration checkpoints from two public
puzzles. These are not new solutions or blinded agent evaluations.

1. GSMG's published 14x14 matrix: 8 corner/direction choices x 2 polarities x 2
   bit orders = 32 recipes. The checkpoint uses the known challenge hostname,
   not the entire answer. One recipe recovers the published path. The final four
   bits are reported as `0000`; they are not silently discarded. The input is a
   public binary transcription, not the original image.
2. Two published SalPhaseIon number strings: explicit character-to-digit mapping
   followed by whole-integer decimal decoding reproduces their published texts.
3. Kryptos K1: with the known keyed alphabet and a retrospectively supplied
   ten-character plaintext prefix, period 10's key is determined. Its consequences
   reproduce the unused suffix. Selecting the correct family/period is not an
   autonomous discovery result and K4 is not attacked or assessed here.

Tests additionally compare cribs to exhaustive key enumeration, Bifid to a
separate coordinate-string implementation, and spiral traversal to independent
boundary peeling. Invalid inputs, partial work, output-contract failures and
cursor behavior have regression checks.

Fixture provenance (commit/blob IDs and representation changes) is in
`examples/data/cryptic-checkpoints.json`. Ciphertext bytes and numerical mappings
are public research data; no original media, long author prose, wallet secrets or
unpublished prize solutions are included. Source labels are not cryptographic
authentication of the author or challenge.

## The next usefulness gate

Do not make operation count, test count, Python version or inner-loop speed the
product objective. The gate is: **does the same agent, on the same stalled task,
produce more independently validated progress at the same budget?**

Build a task pack from real stalled investigations, with four separated tracks:

| Track | Success criterion |
| --- | --- |
| Known-step replay | Exact public checkpoint from archived evidence and stated recipe |
| Mechanism recovery | Recover a withheld recipe on fresh instances; answers inaccessible to the solver |
| Diagnostic counterfactuals | Identify wrong extraction, invented assumptions or non-discriminating transformations |
| Live frontier | Produce a genuinely new independently checkable consequence or next stage |

Use three conditions: plain coding tools; existing specialist crypto tools;
Polya over the same backends. Give equal model, artifact, wall-time and token
budgets. Split whole authors/series and mechanism families, not just adjacent
puzzle stages. Historical answer availability makes contamination a real concern.
Report per-family verified progress, false discoveries, meaningful eliminated
families, unique candidate programs, and human repair/code-writing time. Include
failed and timed-out trials. No agent-benefit result has been measured here.

### Priorities driven by missing puzzle work

1. **Artifact-to-symbol work:** lossless image channels/bit planes, glyph ambiguity,
   timestamped stereo/spectral views, source offsets, original-artifact hashes.
   Preserve competing observations; vision/audio interpretations remain hypotheses.
2. **Clue-conditioned recipe synthesis:** compose and rank extraction rules using
   source evidence; assess counterfactual sensitivity and unused information.
   Expand beyond the finite supplied recipe products implemented here.
3. **Specialist backends:** adapt established classical-cipher search tools instead
   of rebuilding hill-climbing, language scoring and every cipher family. Check
   licensing, actual execution, conventions and negative controls before claiming
   support. No external tool is integrated by merely mentioning it in these docs.
4. **Real-puzzle acceptance adapters:** pin author artifacts and stage semantics;
   calibrate exact format/KDF/checksum/address checks independently. A final
   address comparator does not tell us how to derive the candidate.
5. **Frontier task evaluation:** prioritize the preceding work according to measured
   failures, not whichever named puzzle currently receives the most attention.

Modern cryptographic security challenges need their own research track. A
formalized missing-share or key-search challenge is not made tractable simply
by placing it in a SAT solver. Look for additional public structure, permitted
implementation weaknesses or evidence; keep computational findings and security
assumptions separate. Do not confuse public puzzle authorization with permission
to sweep unrelated wallets or query unrelated services.

## Sources

- GSMG community transcriptions and checkpoints:
  https://github.com/puzzlehunt/gsmgio-5btc-puzzle/blob/fb92dd15487c6e2d275adb8c923698b7166c328e/README.md
- Independently maintained K1 ciphertext fixture:
  https://github.com/stblake/colossus/blob/main/ciphers/kryptos/K1.txt
  (pinned blob: f3a9f22168082933208369a865adf83dd5818db4).
- Colossus's documented classical-cipher portfolio (a prospective adapter, not
  an included dependency): https://github.com/stblake/colossus
- PuzzleWorld's distinction between open-ended mechanism discovery and
  well-specified tasks: https://arxiv.org/abs/2506.06211
