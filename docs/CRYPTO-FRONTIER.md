# Crypto-puzzle usefulness: from evidence to a checked experiment

A faster automata kernel is not a GSMG breakthrough. A tool that applies Bifid
with a supplied square is not a tool that discovers the intended square. Judge
Polya by stalled investigation work it removes, not operation or test counts.

The existing cipher/recipe tools are now on main. This increment adds a raw-PNG
and exact-target bridge while leaving the hard mechanism-discovery problem explicit.

## Use immediately

```bash
python -m pip install -e ".[imaging]"
python -m polya inspect artifact.png_bitplane
python -m polya inspect mechanism.plan_scan
python -m polya inspect crypto.openssl_scan
python -m examples.crypto_frontier_demo
```

An agent can extract a native PNG channel bit plane, compose grid/cipher recipes,
serialize the resulting candidates as exact bytes, and check declared gates.
It does not need to reinterpret output as English or write a Bitcoin checker.
The demo now declares and executes this path through `mechanism.plan_scan`, with
explicit typed references, binary conversions, source-coordinate derivations and
safe resumption. See [typed plans and execution-backed history](TYPED-PLANS.md).

`artifact.png_bitplane` accepts canonical base64 bytes of a single-frame 8-bit
PNG. Choose the native channel and bit explicitly. The result preserves source
and sample hashes, dimensions and the pixel-coordinate mapping. There is no
resizing, thresholding, palette expansion, EXIF orientation or automatic OCR.
A PNG sample index is not a byte offset in the compressed file. Pillow is optional;
its installed version is included in the implementation fingerprint.

`crypto.target_check` compares a SHA256 commitment or explicit P2PKH reading.
Bitcoin/Litecoin-style version bytes and compressed/uncompressed SEC encodings
are explicit. A checksum-valid target is not proof of public-puzzle authorization.
Only feed public challenge targets or data you are authorized to investigate.
There are no transactions, network queries or private-key exports.

`crypto.openssl_scan` tests a finite candidate-by-lock product. Candidate IDs and
sources survive repeated byte values. Identical decryptions are reused, but each
target is checked separately; shared work is not independent evidence. Supported
password modes are raw bytes, lowercase SHA256 hex bytes, and raw SHA256 bytes.
The cipher is AES-256-CBC with legacy EVP_BytesToKey count=1 and explicit MD5 or
SHA256 digest, not PBKDF2 or generalized CryptoJS Rijndael.

Every lock requires a known-answer calibration ciphertext, candidate and plaintext
hash. Controls run before candidate trials. A failed calibration produces no
candidate negatives. Synthetic controls validate implementation consistency;
published controls additionally test compatibility with the cited historical
artifact. Neither proves that an unknown final lock uses the same convention.

Padding-valid bytes are sent directly to the declared target reading. There is
no language, printability, entropy or visual-pattern gate. Results distinguish
TARGET_MATCH, NO_TARGET_MATCH, NO_VALID_PADDING, and READING_NOT_APPLICABLE.
Operational failures propagate; they are not reported as unsuccessful hypotheses.
No candidate or plaintext bytes are returned by the scanner, only IDs and hashes.

Budgets cover at most 256 candidates, eight lock/readings and 512 trials per call.
The byte budget charges ciphertext bytes before each uncached decryption,
including calibrations. Runtime limits are cooperative, not process isolation.
Results specify the tested half-open interval. Resuming needs `start` and the
previous `expected_plan_id`; changing candidates, targets, conventions, sources,
or the implementation invalidates that ID. An exhausted suffix is not a claim
that the earlier prefix was tested. Keep and audit all page receipts.

## GSMG handoff: test generated hypotheses, not another dictionary

```bash
python -m examples.gsmg_gate --candidates candidates.json
```

`candidates.json` is a list like this (the value is an illustration, not a lead):

```json
[{"id":"experiment-17/recipe-4","value_hex":"0041ff",
  "source":"original artifact SHA256 and extraction recipe reference"}]
```

The profile uses the published SalPhaseIon ciphertext and target, with four
explicit plaintext readings and SHA256 EVP as a **hypothesis**. It reproduces
the earlier phase-2 control. It does not assume SHA256 is proven for the final
lock; evaluating another digest requires a calibration valid for that convention.
It does not claim to cover the second 80-byte lock, Dualite, every possible
plaintext reduction, or the separate planted-address route. Add independently
sourced profiles rather than silently merging these different hypotheses.

For more than 128 candidates, this four-reading profile needs multiple scan
pages; use the Python API's start/expected_plan_id or the normal JSON operation
interface. Do not claim a complete negative from the first 512 trials.

The known public GSMG SEC key is separately checked against its published
address. That validates address derivation without recovering a private key.
The phase-2 expected plaintext hash was reproduced with the independent OpenSSL
CLI. Its fixture records the upstream blob ID; no upstream oracle code is run.

## What was actually demonstrated

Three fresh synthetic images contain binary passwords under withheld choices
of RGB channel, sample bit, traversal, polarity and bit order. The search gets
only the image, ciphertext, target and an unrelated known control. It enumerates
192 declared parameter programs per case and identifies one target-matching
candidate in each. A wrong-target case retains valid-padding outputs but returns
no matches. PNGs were encoded by an independent stdlib writer, and ciphertexts
were generated by the OpenSSL executable, not the library's encryption function.

This is a useful integration test: raw artifact to a cryptographic endpoint,
not a demonstration with a supplied final password. It is still a **supplied-
grammar parameter search**, not learned mechanism discovery, a blinded LLM
benchmark, or a newly solved open puzzle. The cases are public regression data,
not a permanently held-out benchmark. Regenerate secret evaluation instances
outside the solver's workspace for a credible agent comparison.

## Development priority, in order

1. **Failure-driven task bank.** Capture actual stalled requests from agents:
   original artifacts, what is established, what is uncertain, required outputs,
   existing tool baselines and explicit acceptance checks. Separate replay from
   live-frontier work. No new operation without a task it can unblock.
2. **Mechanism synthesis.** Search source-grounded programs that select, reorder,
   map, combine and reduce evidence. Generate alternatives from the clues, rank
   by stated assumptions and unused-evidence predictions, and execute with exact
   oracles. `mechanism.scan` evaluates supplied recipes; it does not generate them.
3. **Specialist cryptanalysis.** Integrate rather than reimplement high-quality
   unknown-key search for classical ciphers. Colossus/AZDecrypt/CrypTool-style
   engines are candidates, not installed dependencies. Verify their conventions,
   licensing, output parsing, deterministic seeds and negative controls. English
   scores are not appropriate for every binary/seed/key-bearing layer.
4. **Semantic deduplication and evidence sensitivity.** Expose when different
   recipes yield the same bytes, ignore a clue, or are invariant under the tested
   rearrangement. Add algebraic simplifications only with equivalence checks.
   Aggregate equivalent work without counting it as corroborating evidence.
5. **Broader crypto profiles.** BIP39 vocabulary/checksum and constrained word
   order, historical KDF/serialization profiles, book-index extraction and
   timestamped audio symbols. Prioritize across different puzzle authors/series,
   not a generic Sudoku/automata score or one famous puzzle.

Keep SAT/SMT and automata as tools for justified structured subproblems. Neither
an opaque final hash nor a raw ciphertext becomes informative merely by encoding
it in SAT or naming its checker a learning oracle.

## The 10x gate

Use equal models, tools, hardware, source access, token and time budgets across:
plain code; existing specialist tools; Polya using those same engines.
Measure validated new checkpoints or consequences, repair/code-writing effort,
repeat work and false breakthroughs, separately by puzzle family. A target is
10x less total cost for the same verified result, or more verified progress at
fixed cost; no 10x result is asserted by this increment.

Historical replay, fresh mechanism recovery, misleading controls and live
frontiers are four separate scoreboards. Known solutions test correctness;
withheld instances test recovery; unsolved cases test genuinely new progress.
Replaying an already solved stage does not move an unsolved case forward.

## Sources and evidence boundaries

- GSMG public constants: `floflo777/open-crypto-puzzles`,
  `1-big-prizes/gsmg-io-5btc-puzzle/tools/oracle.py`, blob
  `652afe0739250ef14e6c60c5f0e50987568789b7`. The README, code comments and research
  ledger have differing historical claims; retain versions rather than promote
  a header comment or self-test into a universal rule about the final layer.
- Actual frontier and invalidated negative-history notes:
  https://github.com/floflo777/open-crypto-puzzles/blob/main/1-big-prizes/gsmg-io-5btc-puzzle/analysis/leads.md
- Specialist classical-cipher search: https://github.com/stblake/colossus
- Open-ended mechanism discovery versus supplied-rule tasks:
  https://arxiv.org/abs/2506.06211
