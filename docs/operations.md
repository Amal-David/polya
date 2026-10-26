# Operation reference

Polya registers 56 operations in 24 families. This file is generated from `polya.catalog.REGISTRY` by `scripts/generate_operations_doc.py`; do not edit it by hand. Run `polya inspect ID --schema` for the full JSON schema of one operation.

Families: [artifact](#artifact), [automata](#automata), [backends](#backends), [bits](#bits), [bytes](#bytes), [candidate](#candidate), [casepack](#casepack), [cipher](#cipher), [constraints](#constraints), [council](#council), [crypto](#crypto), [evidence](#evidence), [experiment](#experiment), [grid](#grid), [hypotheses](#hypotheses), [jacobian](#jacobian), [mechanism](#mechanism), [method](#method), [pattern](#pattern), [specialist](#specialist), [symbolic](#symbolic), [text](#text), [utility](#utility), [verify](#verify).

## artifact

### `artifact.png_bitplane`

**Extract a lossless PNG sample bit plane.** Version 1; cacheable: yes.

Preserve original image hash and pixel coordinates while extracting a selected native channel/bit.

Postcondition: Exact supplied PNG sample plane, not automatic steganography detection or a solution.

Limits:

- 393216 encoded-source bytes, at most 65536 decoded pixels
- 8-bit single-frame PNG only
- Pillow extra.

Required inputs:

- `png_base64`: string
- `channel`: one of `"L"`, `"R"`, `"G"`, `"B"`, `"A"`, `"index"`
- `bit`: integer

Optional inputs:

- `max_pixels`: integer, default `16384`

Output fields: `text`, `width`, `height`, `mode`, `channel`, `bit`, `source_sha256`, `samples_sha256`, `coordinates`, `scope`.

## automata

### `automata.distinguish`

**Find a distinguishing experiment.** Version 1; cacheable: no.

Search the reachable product for a shortest distinguishing input sequence.

Postcondition: Witnesses are independently replayed. EQUIVALENT requires full reachable-product exhaustion; limits return UNKNOWN.

Limits:

- Product-state,time,and optional depth budgets. Models only
- no live queries.

Required inputs:

- `left`: Machine
- `right`: Machine

Optional inputs:

- `max_pairs`: integer, default `100000`
- `max_depth`: integer or null, default `null`
- `timeout_ms`: integer, default `5000`

Output fields: `status`, `word`, `left_replay`, `right_replay`, `expanded_pairs`, `discovered_pairs`, `shortest`, `complete`, `reason`, `scope`.

### `automata.from_runs`

**Build a binary run-length rule.** Version 1; cacheable: yes.

Construct a DFA from caller-specified consecutive filled-cell groups.

Postcondition: Recognizes exactly the supplied positive run lengths, with optional leading/trailing zeros.

Limits:

- 64 runs, each <=128, at most1000 generated states.

Required inputs:

- `runs`: array of integer

Output fields: `machine`, `scope`.

Example input:

```json
{
  "runs": [
    2,
    1
  ]
}
```

### `automata.learn_local`

**Learn a local hidden-state simulator.** Version 1; cacheable: no.

Learn a Mealy hypothesis through a guarded reset/step interface.

Postcondition: Finite conformance only, never global equivalence. Native learner is included; AALpy is optional.

Limits:

- Only local simulator inputs via tools
- membership,step,test,state,round,and cooperative time budgets.

Required inputs:

- `machine`: Machine

Optional inputs:

- `learner`: one of `"native"`, `"aalpy"`, default `"native"`
- `max_depth`: integer, default `5`
- `max_queries`: integer, default `10000`
- `max_steps`: integer, default `100000`
- `max_equivalence_tests`: integer, default `10000`
- `timeout_ms`: integer, default `10000`
- `max_rounds`: integer, default `32`
- `max_states`: integer, default `64`

Output fields: `status`, `reason`, `machine`, `learner`, `global_equivalence_proven`, `complete`, `tested_max_depth`, `stats`, `scope`.

### `automata.simulate`

**Replay a deterministic model.** Version 1; cacheable: yes.

Replay DFA acceptance or Mealy input/output behavior.

Postcondition: Exact model replay; partial DFA edges reject, while Mealy machines must be total.

Limits:

- At most10000 input symbols
- validated deterministic transitions.

Required inputs:

- `machine`: Machine
- `word`: array of integer or string

Output fields: `final_state`, `state_trace`, `outputs`, `accepted`, `scope`.

Example input:

```json
{
  "machine": {
    "kind": "dfa",
    "states": [
      "even",
      "odd"
    ],
    "alphabet": [
      0,
      1
    ],
    "initial": "even",
    "accepting": [
      "even"
    ],
    "transitions": [
      {
        "source": "even",
        "symbol": 0,
        "target": "even"
      },
      {
        "source": "even",
        "symbol": 1,
        "target": "odd"
      },
      {
        "source": "odd",
        "symbol": 0,
        "target": "odd"
      },
      {
        "source": "odd",
        "symbol": 1,
        "target": "even"
      }
    ]
  },
  "word": [
    1,
    0,
    1
  ]
}
```

### `automata.simulate_many`

**Replay a batch of sequences.** Version 1; cacheable: yes.

Prepare a detached transition snapshot once for a bounded batch.

Postcondition: Same exact deterministic-model replay as separate calls; not real-world observations.

Limits:

- 256 words, 10000 total symbols, standard output limit. No normalization or deduplication.

Required inputs:

- `machine`: Machine
- `words`: array of array of integer or string

Output fields: `results`, `word_count`, `symbol_count`, `scope`.

## backends

### `backends.inspect`

**Inspect available backends.** Version 1; cacheable: no.

Report runtime availability and supported capabilities.

Postcondition: Availability only, not a claim that an optional dependency passed integration tests.

Limits:

- Local package/library inspection only.

Output fields: `backends`, `scope`.

## bits

### `bits.from_symbols`

**Map an explicit two-symbol alphabet to bits.** Version 1; cacheable: yes.

Map distinct single-code-point zero and one symbols without changing or dropping input.

Postcondition: Exact supplied transformation; not evidence of the intended puzzle mechanism. Every source code point must be one of the two explicitly declared symbols.

Limits:

- 0..65536 Unicode code points
- two distinct single-code-point symbols
- at most 65536 output bits and source offsets
- no normalization.

Required inputs:

- `text`: string
- `zero`: string
- `one`: string

Output fields: `text`, `source_offsets`, `scope`.

### `bits.invert`

**Apply an explicit binary inversion.** Version 1; cacheable: yes.

Preserve or invert every supplied binary digit while retaining code-point offsets.

Postcondition: Exact supplied transformation; not evidence of the intended puzzle mechanism. invert=false preserves the input; invert=true swaps 0 and 1.

Limits:

- 0..65536 ASCII binary digits
- at most 65536 output digits and source offsets
- no normalization.

Required inputs:

- `text`: string

Optional inputs:

- `invert`: boolean, default `false`

Output fields: `text`, `source_offsets`, `scope`.

### `bits.pack`

**Pack exact binary groups into bytes.** Version 1; cacheable: yes.

Pack eight-bit groups with explicit bit order and incomplete-tail handling; preserve zero bytes.

Postcondition: Exact supplied transformation; not evidence of the intended puzzle mechanism. Source offsets list contributing bits from most to least significant; no text decoding.

Limits:

- 0..65536 ASCII binary digits
- fixed 8-bit groups
- at most 8192 bytes, 16384 hex digits, 65536 contributing offsets and 7 explicitly dropped tail offsets.

Required inputs:

- `text`: string

Optional inputs:

- `bit_order`: one of `"msb"`, `"lsb"`, default `"msb"`
- `tail`: one of `"reject"`, `"drop"`, default `"reject"`

Output fields: `hex`, `byte_length`, `source_offsets`, `dropped_offsets`, `consumed_bits`, `bit_order`, `tail`, `scope`.

Example input:

```json
{
  "text": "0100100001101001"
}
```

## bytes

### `bytes.decode`

**Decode bytes.** Version 1; cacheable: yes.

Decode strict canonical base64 or hexadecimal.

Postcondition: Exact bytes under the selected encoding; no whitespace repair or text guessing.

Limits:

- 65536 decoded bytes.

Required inputs:

- `value`: string
- `encoding`: one of `"hex"`, `"base64"`

Output fields: `hex`, `byte_length`, `sha256`, `encoding`.

Example input:

```json
{
  "value": "SGVsbG8=",
  "encoding": "base64"
}
```

### `bytes.decode_text`

**Decode exact bytes as text.** Version 1; cacheable: yes.

Decode strict hexadecimal bytes under an explicit codec, retaining source byte spans.

Postcondition: Exact encoding under the specified codec; no normalization or error repair.

Limits:

- 16384 source bytes
- only ascii, utf-8 and latin-1. Invalid byte sequences are errors.

Required inputs:

- `value_hex`: string
- `codec`: one of `"ascii"`, `"utf-8"`, `"latin-1"`

Output fields: `text`, `byte_length`, `codepoint_length`, `codepoint_byte_spans`, `codec`, `scope`.

Example input:

```json
{
  "value_hex": "41e99baa",
  "codec": "utf-8"
}
```

### `bytes.from_radix`

**Decode radix groups or a whole integer.** Version 1; cacheable: yes.

Postcondition: Exact supplied transformation; not evidence of the intended puzzle mechanism.

Limits:

- Bounded text, explicit alphabets and normalization
- inspect input schema.

Required inputs:

- `text`: string
- `radix`: one of `2`, `8`, `10`, `16`

Optional inputs:

- `mode`: one of `"integer"`, `"groups"`, default `"integer"`
- `group_width`: integer, default `8`
- `bit_order`: one of `"msb"`, `"lsb"`, default `"msb"`
- `tail`: one of `"reject"`, `"report"`, default `"reject"`
- `codec`: one of `"ascii"`, `"utf-8"`, `"latin-1"`, default `"ascii"`
- `min_bytes`: integer, default `1`

Output fields: `hex`, `text`, `byte_count`, `consumed_digits`, `trailing_digits`, `leading_zero_digits`, `scope`.

Example input:

```json
{
  "text": "48656c6c6f",
  "radix": 16
}
```

### `bytes.slice`

**Select an explicit half-open byte range.** Version 1; cacheable: yes.

Select bytes by start/stop offsets and report every discarded prefix and suffix range.

Postcondition: Exact supplied transformation; not evidence of the intended puzzle mechanism. Requires 0 <= start <= stop <= source byte length; no implicit truncation.

Limits:

- 0..32768 even hexadecimal digits (0..16384 source bytes)
- at most 16384 selected bytes and source offsets
- at most 2 nonempty half-open dropped ranges
- no whitespace or prefix.

Required inputs:

- `value_hex`: string
- `start`: integer
- `stop`: integer

Output fields: `hex`, `byte_length`, `source_offsets`, `dropped_ranges`, `scope`.

## candidate

### `candidate.expand`

**Page a finite candidate product.** Version 1; cacheable: yes.

Expand explicit slot alternatives with stable indices and complete derivation choices.

Postcondition: Exactly the requested half-open index range of the ordered slot product. Duplicates preserved.

Limits:

- 32 slots, <=1000 outputs/page, 100000 output codepoints. Mixed-radix direct seeking.

Required inputs:

- `slots`: array of array of string

Optional inputs:

- `separator`: string, default `""`
- `start`: integer, default `0`
- `limit`: integer, default `100`

Output fields: `total_assignments`, `start`, `stop`, `emitted`, `candidates`, `next_start`, `complete`, `status`, `scope`.

Example input:

```json
{
  "slots": [
    [
      "red",
      "blue"
    ],
    [
      "cat",
      "dog"
    ]
  ],
  "separator": " "
}
```

## casepack

### `casepack.inspect`

**Inspect an evidence-grounded investigation packet.** Version 1; cacheable: yes.

Verify artifact hashes; keep missing evidence, hypotheses, retractions and questions explicit in a compact handoff.

Postcondition: Consistency of caller-supplied evidence, not authenticity or a solve.

Limits:

- 32 artifacts,64 statements,8 controls,900KB total.

Required inputs:

- `case`: CasePack

Output fields: `case_id`, `manifest_sha256`, `ready`, `blocking_artifacts`, `artifacts`, `question`, `statements`, `open_questions`, `calibration_count`, `scope`.

Example input:

```json
{
  "case": {
    "id": "public-calibration",
    "question": "Can this environment replay the known control?",
    "artifacts": [
      {
        "id": "cipher",
        "encoding": "utf8",
        "content": "LXFOPVEFRNHR",
        "sha256": "8780596527ca581b1cc0b3a355de043ba9538e73c3ed4321c9505d19d4d528f7",
        "source": "public Vigenere control"
      }
    ],
    "calibrations": [
      {
        "id": "known-answer",
        "operation_id": "cipher.polyalphabetic",
        "inputs": {
          "key": "LEMON"
        },
        "artifact_bindings": {
          "text": "cipher"
        },
        "output_field": "text",
        "expected_value_sha256": "07518591346f736bb4ff75689b65b29f477a0a76b361cfaf33e88637835ce70b",
        "source": "known plaintext"
      }
    ]
  }
}
```

### `casepack.replay`

**Replay known calibration checkpoints.** Version 1; cacheable: no.

Check required evidence first, then execute bounded allowlisted controls; no upstream code or network.

Postcondition: Only declared known controls tested; no conclusion about unknown answers.

Limits:

- 8 allowlisted calls,shared cooperative 1..60000ms deadline.

Required inputs:

- `case`: CasePack

Optional inputs:

- `timeout_ms`: integer, default `5000`

Output fields: `status`, `inspection`, `calibrations`, `complete`, `scope`.

Example input:

```json
{
  "case": {
    "id": "public-calibration",
    "question": "Can this environment replay the known control?",
    "artifacts": [
      {
        "id": "cipher",
        "encoding": "utf8",
        "content": "LXFOPVEFRNHR",
        "sha256": "8780596527ca581b1cc0b3a355de043ba9538e73c3ed4321c9505d19d4d528f7",
        "source": "public Vigenere control"
      }
    ],
    "calibrations": [
      {
        "id": "known-answer",
        "operation_id": "cipher.polyalphabetic",
        "inputs": {
          "key": "LEMON"
        },
        "artifact_bindings": {
          "text": "cipher"
        },
        "output_field": "text",
        "expected_value_sha256": "07518591346f736bb4ff75689b65b29f477a0a76b361cfaf33e88637835ce70b",
        "source": "known plaintext"
      }
    ]
  }
}
```

## cipher

### `cipher.bifid`

**Transform Bifid with an explicit square and period.** Version 1; cacheable: yes.

Postcondition: Exact supplied transformation; not evidence of the intended puzzle mechanism.

Limits:

- Bounded text, explicit alphabets and normalization
- inspect input schema.

Required inputs:

- `text`: string
- `square`: string
- `period`: integer

Optional inputs:

- `action`: one of `"encrypt"`, `"decrypt"`, default `"decrypt"`

Output fields: `text`, `block_lengths`, `scope`.

Example input:

```json
{
  "text": "HAAEVSLDSP",
  "square": "ABCDEFGHIKLMNOPQRSTUVWXYZ",
  "period": 5
}
```

### `cipher.checkerboard`

**Decode an explicit prefix-free checkerboard.** Version 1; cacheable: yes.

Postcondition: Exact supplied transformation; not evidence of the intended puzzle mechanism.

Limits:

- Bounded text, explicit alphabets and normalization
- inspect input schema.

Required inputs:

- `text`: string
- `codes`: object of string

Output fields: `text`, `source_spans`, `consumed_digits`, `scope`.

### `cipher.periodic_cribs`

**Eliminate periodic keys using source-labelled cribs.** Version 1; cacheable: yes.

Postcondition: Exact necessary key constraints and local contradictions for the declared cipher family; no language-model score.

Limits:

- Bounded text, explicit alphabets and normalization
- inspect input schema.

Required inputs:

- `text`: string
- `cribs`: array of Crib
- `periods`: array of integer

Optional inputs:

- `alphabet`: string, default `"ABCDEFGHIJKLMNOPQRSTUVWXYZ"`
- `variant`: one of `"vigenere"`, `"beaufort"`, `"variant_beaufort"`, default `"vigenere"`

Output fields: `periods`, `crib_equations`, `scope`.

### `cipher.periodic_search`

**Propose unknown periodic-cipher keys.** Version 1; cacheable: no.

Score all column shifts against caller-supplied reference text, then retain a bounded beam and re-encrypt every emitted candidate.

Postcondition: Heuristic key/plaintext proposals only; exact re-encryption does not certify intended meaning.

Limits:

- 8192 ciphertext symbols,16 periods<=32,64-symbol alphabet,128 beam,16 results
- work/time bounds.

Required inputs:

- `text`: string
- `reference_text`: string
- `reference_source`: string
- `periods`: array of integer

Optional inputs:

- `alphabet`: string, default `"ABCDEFGHIJKLMNOPQRSTUVWXYZ"`
- `variant`: one of `"vigenere"`, `"beaufort"`, `"variant_beaufort"`, default `"vigenere"`
- `shifts_per_column`: integer, default `3`
- `beam_width`: integer, default `32`
- `top_k`: integer, default `5`
- `max_work`: integer, default `2000000`
- `timeout_ms`: integer, default `5000`

Output fields: `candidates`, `completed_periods`, `candidate_keys_evaluated`, `work_units`, `termination_reason`, `complete_declared_search`, `full_keyspace_exhausted`, `reference_source`, `scope`.

### `cipher.polyalphabetic`

**Transform Vigenere or Beaufort with an explicit alphabet.** Version 1; cacheable: yes.

Postcondition: Exact supplied transformation; not evidence of the intended puzzle mechanism.

Limits:

- Bounded text, explicit alphabets and normalization
- inspect input schema.

Required inputs:

- `text`: string
- `key`: string

Optional inputs:

- `alphabet`: string, default `"ABCDEFGHIJKLMNOPQRSTUVWXYZ"`
- `variant`: one of `"vigenere"`, `"beaufort"`, `"variant_beaufort"`, default `"vigenere"`
- `action`: one of `"encrypt"`, `"decrypt"`, default `"decrypt"`

Output fields: `text`, `source_offsets`, `scope`.

Example input:

```json
{
  "text": "LXFOPVEFRNHR",
  "key": "LEMON"
}
```

## constraints

### `constraints.plan`

**Plan declared local factors.** Version 1; cacheable: yes.

Count product and local-factor work; report connected components.

Postcondition: Counts for caller-supplied domains and factor scopes. Does not establish real-puzzle independence.

Limits:

- Counts only
- no evaluation. Survivor joins still add work.

Required inputs:

- `domains`: object of array of string
- `scopes`: array of array of string

Output fields: `joint_assignments`, `factor_local_combinations`, `sum_factor_local_combinations`, `components`, `zero_arity_factors`, `assumption_notice`.

### `constraints.solve`

**Solve a finite table constraint system.** Version 1; cacheable: yes.

Propagate explicit allowed tables and enumerate assignments under budgets.

Postcondition: Solutions of the declared table system only; COMPLETE empty output rejects that system, not the puzzle.

Limits:

- Explicit node/result/propagation/output budgets and admission limits
- PARTIAL never means unsatisfiable.

Required inputs:

- `domains`: object of array of string
- `constraints`: array of Table

Optional inputs:

- `max_solutions`: integer, default `100`
- `max_nodes`: integer, default `100000`

Output fields: `status`, `complete`, `solutions`, `nodes_visited`, `termination_reason`, `propagation_checks`, `propagation_check_limit`, `output_bytes`, `output_byte_limit`, `exact_scope`.

Example input:

```json
{
  "domains": {
    "a": [
      "0",
      "1"
    ],
    "b": [
      "0",
      "1"
    ]
  },
  "constraints": [
    {
      "scope": [
        "a",
        "b"
      ],
      "allowed": [
        [
          "0",
          "1"
        ],
        [
          "1",
          "0"
        ]
      ]
    }
  ]
}
```

## council

### `council.prepare`

**Prepare independent council tasks.** Version 1; cacheable: yes.

Prepare four blind role tasks; the calling host invokes agents, not this operation.

Postcondition: Job contracts only; no agent invocation.

Limits:

- 4 roles
- 12000-character brief
- 64 bounded source references.

Required inputs:

- `brief`: string
- `source_refs`: array of string

Output fields: `council_id`, `jobs`, `scope`.

Example input:

```json
{
  "brief": "Find why complete puzzle experiments need custom glue.",
  "source_refs": [
    "repo@reviewed-head"
  ]
}
```

### `council.prioritize`

**Prioritize cross-critiqued feature proposals.** Version 1; cacheable: yes.

Keep objections, dependencies and missing reviews visible; no majority vote proves a claim.

Postcondition: Advisory ordering of supplied estimates, not independent agreement or approval.

Limits:

- 4 reports/phase,8 proposals/role,32 objections/role.

Required inputs:

- `proposals`: array of Proposal
- `critiques`: array of Critique
- `source_refs`: array of string

Output fields: `features`, `complete_review`, `missing_feature_reviews`, `missing_proposals`, `missing_critiques`, `abstentions`, `scope`.

## crypto

### `crypto.bip39_seed`

**Evaluate the BIP39 seed function.** Version 1; cacheable: yes.

NFKD + PBKDF2-HMAC-SHA512; vocabulary/checksum validation is a separate question.

Postcondition: Exact 64-byte seed-function output; does not certify a valid mnemonic or target address.

Limits:

- 8192 codepoints per field
- 2048 iterations.

Required inputs:

- `mnemonic`: string
- `passphrase`: string

Output fields: `seed_hex`, `normalization`, `iterations`, `mnemonic_was_normalized`, `passphrase_was_normalized`, `checksum_checked`, `vocabulary_checked`, `scope`.

### `crypto.openssl_decrypt`

**Evaluate an explicit AES password.** Version 1; cacheable: yes.

AES-256-CBC with legacy EVP_BytesToKey, count=1, explicit digest and password bytes.

Postcondition: Deterministic decrypt under declared parameters. Padding is a signal, never a solution verdict.

Limits:

- 65536 blob bytes, 4096 password bytes. Not PBKDF2 or nonstandard CryptoJS Rijndael.

Required inputs:

- `blob_hex`: string
- `password_hex`: string
- `digest`: one of `"md5"`, `"sha256"`

Output fields: `plaintext_padded_hex`, `plaintext_hex`, `padding_valid`, `padding_bytes`, `cipher`, `kdf`, `iterations`, `digest`, `evidence_kind`, `scope`.

### `crypto.openssl_inspect`

**Inspect legacy salted framing.** Version 1; cacheable: yes.

Recognize Salted__ with 8-byte salt and 16-byte-aligned ciphertext.

Postcondition: Framing only; cipher, key size, digest and KDF remain unknown.

Limits:

- 65536 bytes
- legacy 8-byte-salt framing only.

Required inputs:

- `blob_hex`: string

Output fields: `format`, `salt_hex`, `ciphertext_hex`, `ciphertext_bytes`, `unknown_parameters`, `scope`.

### `crypto.openssl_scan`

**Evaluate calibrated candidates against multiple locks.** Version 1; cacheable: no.

Test candidate bytes using exact password conventions, retained derivations and target checks.

Postcondition: Only the supplied candidates, targets, readings and calibrated AES-256-CBC/EVP_BytesToKey count=1 conventions were tested. No English filter is used. Padding and calibration are not a solved puzzle. Source labels are caller claims.

Limits:

- 256 candidates,8 locks,512 trials,16 matches
- byte/time budgets include controls.

Required inputs:

- `candidates`: array of Candidate
- `locks`: array of Lock

Optional inputs:

- `start`: integer, default `0`
- `expected_plan_id`: string or null, default `null`
- `max_trials`: integer, default `256`
- `max_matches`: integer, default `16`
- `max_decrypted_bytes`: integer, default `1048576`
- `timeout_ms`: integer, default `5000`

Output fields: `status`, `plan_id`, `calibrations`, `trials`, `matches`, `range`, `next_start`, `complete`, `range_exhausted`, `termination_reason`, `crypto_calls`, `reused_calls`, `decrypted_bytes`, `scope`.

### `crypto.target_check`

**Check an exact cryptographic puzzle target.** Version 1; cacheable: yes.

Check raw-byte SHA256 or an explicit secp256k1/P2PKH reading without a language filter.

Postcondition: Only the supplied candidates, targets, readings and calibrated AES-256-CBC/EVP_BytesToKey count=1 conventions were tested. No English filter is used. Padding and calibration are not a solved puzzle. Source labels are caller claims.

Limits:

- 16384 bytes
- explicit reading/compression/version
- no network or transactions.

Required inputs:

- `candidate_hex`: string
- `target`: Target

Output fields: `match`, `outcome`, `observed`, `candidate_sha256`, `scope`.

## evidence

### `evidence.padding_null`

**Compute chance padding expectation.** Version 1; cacheable: yes.

Expected padding hits under a uniform wrong-key final-block model.

Postcondition: Exact rational event probability and floating expected count under a declared null; not a significance test.

Limits:

- <=10^18 trials
- block size <=255 bytes.

Required inputs:

- `trials`: integer

Optional inputs:

- `block_bytes`: integer, default `16`
- `fixed_padding_bytes`: integer or null, default `null`

Output fields: `probability_numerator`, `probability_denominator`, `probability`, `trials`, `expected_padding_hits`, `probability_scientific`, `expected_padding_hits_scientific`, `float_underflow`, `assumption`, `evidence_kind`.

## experiment

### `experiment.from_comparison`

**Turn compared hypotheses into observable tests.** Version 1; cacheable: yes.

Bind a hypotheses.compare envelope to caller-specified observation sources and costs; produce typed predictions for experiment.rank_tests.

Postcondition: Receipt and witness consistency for conditional test inputs, not authenticated execution, a new forced-value proof or acquired evidence.

Limits:

- Comparison contract version 3 only
- 2-8 case IDs of 1-64 characters, 128 observable variables, existing 1 MB input/output admission bounds
- no solver work.

Required inputs:

- `comparison_inputs`: CompareInput
- `comparison`: ComparisonEnvelope
- `observables`: array of Observable

Optional inputs:

- `criterion`: one of `"separation_per_cost"`, `"separation"`, default `"separation_per_cost"`

Output fields: `rank_inputs`, `comparison_identity`, `case_evidence`, `observation_acquired`, `outcome_encoding`, `scope`.

### `experiment.rank_tests`

**Choose a discriminating next experiment.** Version 1; cacheable: yes.

Rank explicit predicted disagreements per cost; preserve missing predictions instead of treating them as evidence.

Postcondition: Conditional test ranking, not proof or measured chance of solving.

Limits:

- 64 hypotheses,128 tests
- finite pairwise accounting.

Required inputs:

- `hypotheses`: array of Hypothesis
- `tests`: array of Test

Optional inputs:

- `criterion`: one of `"separation_per_cost"`, `"separation"`, default `"separation_per_cost"`

Output fields: `tests`, `next_test_id`, `status`, `weight_convention`, `scope`.

Example input:

```json
{
  "hypotheses": [
    {
      "id": "a",
      "mechanism": "row reading",
      "source": "clue"
    },
    {
      "id": "b",
      "mechanism": "column reading",
      "source": "clue"
    }
  ],
  "tests": [
    {
      "id": "first-symbol",
      "question": "What is the first extracted symbol?",
      "cost": 1,
      "predictions": {
        "a": "A",
        "b": "B"
      },
      "source": "model predictions"
    }
  ]
}
```

## grid

### `grid.read`

**Read a rectangular text grid.** Version 1; cacheable: yes.

Reorder an exact rectangular grid while retaining source offsets.

Postcondition: A permutation of source codepoints under the declared grid and reading order.

Limits:

- 65536 codepoints
- no padding or truncation.

Required inputs:

- `text`: string
- `rows`: integer
- `columns`: integer
- `order`: one of `"row"`, `"column"`, `"row_snake"`, `"column_snake"`

Optional inputs:

- `reverse`: boolean, default `false`

Output fields: `text`, `source_offsets`, `unit`, `rows`, `columns`, `order`, `reverse`.

Example input:

```json
{
  "text": "abcdef",
  "rows": 2,
  "columns": 3,
  "order": "column"
}
```

### `grid.traverse`

**Traverse a grid including corner-aware spirals.** Version 1; cacheable: yes.

Postcondition: Exact supplied transformation; not evidence of the intended puzzle mechanism.

Limits:

- Bounded text, explicit alphabets and normalization
- inspect input schema.

Required inputs:

- `text`: string
- `rows`: integer
- `columns`: integer
- `route`: one of `"row"`, `"column"`, `"row_snake"`, `"column_snake"`, `"spiral_cw"`, `"spiral_ccw"`

Optional inputs:

- `corner`: one of `"tl"`, `"tr"`, `"bl"`, `"br"`, default `"tl"`
- `reverse`: boolean, default `false`

Output fields: `text`, `source_offsets`, `source_length`, `scope`.

Example input:

```json
{
  "text": "123456789",
  "rows": 3,
  "columns": 3,
  "route": "spiral_cw"
}
```

## hypotheses

### `hypotheses.compare`

**Compare competing interpretations.** Version 3; cacheable: no.

Analyze named assumption sets and propose differing forced observations.

Postcondition: Proposed observations distinguish only the specified cases. No real observation is acquired.

Limits:

- 2-8 cases, with one shared time/check/reference budget. Empty suggestions do not mean equivalence.

Required inputs:

- `model`: PuzzleModel
- `cases`: object of array of string

Optional inputs:

- `backend`: one of `"auto"`, `"z3"`, `"cpsat"`, `"reference"`, default `"auto"`
- `timeout_ms`: integer, default `5000`
- `max_checks`: integer, default `1000`
- `max_assignments`: integer, default `100000`

Output fields: `status`, `failed_cases`, `cases`, `distinguishing_observations`, `complete`, `scope`.

## jacobian

### `jacobian.find`

**Discover Jacobian math operations.** Version 1; cacheable: no.

Delegate mathematical search or exact inspection to Jacobian's own math.find tool.

Postcondition: Preserves upstream mathematical contracts and errors; no puzzle interpretation verified.

Limits:

- Explicit Jacobian installation
- bounded subprocess startup/output, 1..120s deadline.

Optional inputs:

- `query`: string or null, default `null`
- `operation_id`: string or null, default `null`
- `namespace`: string or null, default `null`
- `limit`: integer, default `5`
- `cursor`: string or null, default `null`
- `search_mode`: one of `"precise"`, `"broad"`, default `"precise"`
- `timeout_ms`: integer, default `20000`

Output fields: `status`, `data`, `error`, `upstream_version`, `upstream_tool`, `release_source_sha`, `scope`.

Example input:

```json
{
  "query": "exact extended gcd for two integers",
  "limit": 3
}
```

### `jacobian.inspect`

**Detect optional Jacobian runtime.** Version 1; cacheable: no.

Check for a reviewed, separately installed mathematical backend without loading it.

Postcondition: Capability detection only; not evidence that an operation ran.

Limits:

- Local executable check, no network or subprocess launch.

Output fields: `executable_found`, `version_pin`, `release_source_sha`, `separate_runtime_required`, `scope`.

### `jacobian.run`

**Execute one inspected Jacobian math operation.** Version 1; cacheable: no.

Delegate one typed mathematical payload to Jacobian's own math.run tool.

Postcondition: Math output and upstream error scope retained. No false claim of independently checked interpretation.

Limits:

- Operator-installed separate runtime, 500KB request, 1.1MB response, 1..180s deadline.

Required inputs:

- `operation_id`: string
- `payload`: object

Optional inputs:

- `timeout_ms`: integer, default `30000`

Output fields: `status`, `data`, `error`, `upstream_version`, `upstream_tool`, `release_source_sha`, `scope`.

## mechanism

### `mechanism.plan_inspect`

**Preflight a typed investigation plan.** Version 1; cacheable: no.

Check source representations, references, constants and search size without executing kernels; return repair diagnostics.

Postcondition: Validation of the supplied grammar only. valid=false is a diagnosis, not a rejected puzzle hypothesis.

Limits:

- Same plan admission limits
- at most 16 diagnostics. No search or target calibration.

Required inputs:

- `plan`: object

Output fields: `valid`, `plan_id`, `recipe_count`, `sources`, `steps`, `issues`, `next_operation`, `scope`.

Example input:

```json
{
  "plan": {
    "sources": [
      {
        "id": "clue",
        "kind": "symbols",
        "value": "LXFOPVEFRNHR",
        "source": "public Vigenere calibration vector"
      }
    ],
    "nodes": [
      {
        "id": "plaintext",
        "alternatives": [
          {
            "operation_id": "cipher.polyalphabetic",
            "bindings": {
              "text": {
                "node": "clue",
                "field": "value"
              }
            },
            "inputs": {
              "key": "LEMON",
              "variant": "vigenere",
              "action": "decrypt"
            },
            "rationale": "two explicitly proposed keys in a known-answer example"
          },
          {
            "operation_id": "cipher.polyalphabetic",
            "bindings": {
              "text": {
                "node": "clue",
                "field": "value"
              }
            },
            "inputs": {
              "key": "LIMES",
              "variant": "vigenere",
              "action": "decrypt"
            },
            "rationale": "two explicitly proposed keys in a known-answer example"
          }
        ]
      },
      {
        "id": "encoded",
        "alternatives": [
          {
            "operation_id": "text.encode",
            "bindings": {
              "text": {
                "node": "plaintext",
                "field": "text"
              }
            },
            "inputs": {
              "codec": "ascii"
            },
            "rationale": "the control specifies ASCII bytes"
          }
        ]
      }
    ],
    "candidate": {
      "node": "encoded",
      "field": "hex"
    },
    "target": {
      "kind": "direct",
      "target": {
        "kind": "sha256",
        "value": "393dfae2845abf5cb0d599ccd1189f57ef56b3fa104e0ae71844d78bccd4e5d2",
        "source": "independent known-answer control"
      }
    }
  }
}
```

### `mechanism.plan_scan`

**Execute typed artifact-to-target plans.** Version 1; cacheable: no.

Compose PNGs, spirals, classical ciphers, radix and strict codec conversions with exact targets. Use mechanism.plan_inspect before searching.

Postcondition: Exact target checks under a supplied finite grammar; interruption and invalid inputs never imply a negative puzzle result.

Limits:

- 4 sources,8 nodes,64 alternatives/node,1M recipes,512 trials,16 matches
- 65536 bit/symbol units,16384 candidate bytes
- time/work/cache/output bounds.

Required inputs:

- `plan`: Plan

Optional inputs:

- `start`: integer, default `0`
- `expected_plan_id`: string or null, default `null`
- `max_trials`: integer, default `256`
- `max_matches`: integer, default `16`
- `max_work`: integer, default `4000000`
- `timeout_ms`: integer, default `5000`

Output fields: `status`, `plan_id`, `recipe_count`, `start`, `stop`, `next_start`, `complete`, `range_exhausted`, `termination_reason`, `trials`, `matches`, `sources`, `coverage`, `conclusion`, `kernel_calls`, `cache_hits`, `work_units`, `scope`.

Example input:

```json
{
  "plan": {
    "sources": [
      {
        "id": "clue",
        "kind": "symbols",
        "value": "LXFOPVEFRNHR",
        "source": "public Vigenere calibration vector"
      }
    ],
    "nodes": [
      {
        "id": "plaintext",
        "alternatives": [
          {
            "operation_id": "cipher.polyalphabetic",
            "bindings": {
              "text": {
                "node": "clue",
                "field": "value"
              }
            },
            "inputs": {
              "key": "LEMON",
              "variant": "vigenere",
              "action": "decrypt"
            },
            "rationale": "two explicitly proposed keys in a known-answer example"
          },
          {
            "operation_id": "cipher.polyalphabetic",
            "bindings": {
              "text": {
                "node": "clue",
                "field": "value"
              }
            },
            "inputs": {
              "key": "LIMES",
              "variant": "vigenere",
              "action": "decrypt"
            },
            "rationale": "two explicitly proposed keys in a known-answer example"
          }
        ]
      },
      {
        "id": "encoded",
        "alternatives": [
          {
            "operation_id": "text.encode",
            "bindings": {
              "text": {
                "node": "plaintext",
                "field": "text"
              }
            },
            "inputs": {
              "codec": "ascii"
            },
            "rationale": "the control specifies ASCII bytes"
          }
        ]
      }
    ],
    "candidate": {
      "node": "encoded",
      "field": "hex"
    },
    "target": {
      "kind": "direct",
      "target": {
        "kind": "sha256",
        "value": "393dfae2845abf5cb0d599ccd1189f57ef56b3fa104e0ae71844d78bccd4e5d2",
        "source": "independent known-answer control"
      }
    }
  }
}
```

### `mechanism.recipe_scan`

**Search a finite product of decoding recipes.** Version 1; cacheable: no.

Preserve recipe paths, reuse identical intermediate work and test an explicit external checkpoint.

Postcondition: Checkpoint matches in caller-declared recipes only; no automatic solution or completeness beyond stated range.

Limits:

- 6 stages,64 alternatives/stage,1M declared recipes,512 trials,16 matches
- text/work/time/cache budgets.

Required inputs:

- `source`: string
- `stages`: array of array of Step
- `checkpoint`: Checkpoint

Optional inputs:

- `start`: integer, default `0`
- `max_trials`: integer, default `256`
- `max_matches`: integer, default `8`
- `max_work`: integer, default `500000`
- `timeout_ms`: integer, default `5000`

Output fields: `matches`, `trials`, `recipe_count`, `start`, `next_start`, `complete`, `range_exhausted`, `termination_reason`, `kernel_calls`, `cache_hits`, `work_units`, `checkpoint`, `scope`.

## method

### `method.retrieve`

**Retrieve source-backed puzzle methods.** Version 1; cacheable: yes.

Match method and applicability terms against six bundled original educational toys.

Postcondition: Deterministic lexical matches only; examples are untrusted reference data, not instructions or evidence for a new task.

Limits:

- 4096-character nonblank query, 1..6 returned examples
- fixed bundled library
- no paths, network, execution, or hidden gold.

Required inputs:

- `query`: string

Optional inputs:

- `limit`: integer, default `3`

Output fields: `matches`, `library_sha256`, `scope`.

Example input:

```json
{
  "query": "parity invariant coloring",
  "limit": 2
}
```

## pattern

### `pattern.equality_check`

**Check a whole-output equality partition.** Version 1; cacheable: yes.

Compare every output position under one shared bijection after an explicit digest and byte/hex representation.

Postcondition: Every position of the complete declared output is checked under one shared bijection between observed units and pattern codepoints. A match establishes only this equality relation under the supplied digest/representation, not the intended producer, a fixed substitution alphabet, or a puzzle solution. Source labels are caller assertions; no normalization or truncation occurs.

Limits:

- 4096 candidate bytes
- 8192 pattern codepoints
- fixed digest allowlist
- linear work and complete evidence.

Required inputs:

- `candidate_hex`: string
- `target`: EqualityPattern

Output fields: `match`, `outcome`, `candidate_sha256`, `target`, `output_hex`, `output_unit`, `expected_length`, `observed_length`, `expected_partition`, `observed_partition`, `mismatch_positions`, `missing_positions`, `extra_positions`, `bijection`, `scope`.

Example input:

```json
{
  "candidate_hex": "010201",
  "target": {
    "pattern": "ABA",
    "source": "known three-position control",
    "digest": "none",
    "representation": "bytes"
  }
}
```

## specialist

### `specialist.verify_proposal`

**Verify a specialist-engine candidate.** Version 1; cacheable: yes.

Check artifact identity and independently re-encrypt periodic-cipher proposals.

Postcondition: Independent re-encryption under supplied conventions, without calling the external solver. All SHA-256 digests cover exact ciphertext/plaintext encoded as UTF-8, without normalization or an added byte-order mark, not original artifact bytes. Checkpoint source labels are caller-supplied and unauthenticated.

Limits:

- Periodic Vigenere/Beaufort only
- 16384 ciphertext characters, 1024 key characters.

Required inputs:

- `engine`: string
- `revision`: string
- `artifact_sha256`: string. SHA-256 of the exact ciphertext encoded as UTF-8, without normalization or an added byte-order mark; not the original artifact bytes.
- `ciphertext`: string
- `plaintext`: string
- `key`: string

Optional inputs:

- `alphabet`: string, default `"ABCDEFGHIJKLMNOPQRSTUVWXYZ"`
- `variant`: one of `"vigenere"`, `"beaufort"`, `"variant_beaufort"`, default `"vigenere"`
- `expected_plaintext_sha256`: string or null, default `null`. Optional SHA-256 commitment to the exact plaintext encoded as UTF-8, without normalization or an added byte-order mark.
- `checkpoint_source`: string or null, default `null`. Caller-supplied, unauthenticated source label for the plaintext commitment; required together with expected_plaintext_sha256.

Output fields: `replay_consistent`, `commitment_match`, `status`, `plaintext_sha256`, `expected_plaintext_sha256`, `checkpoint_source`, `digest_encoding`, `engine`, `revision`, `scope`.

## symbolic

### `symbolic.analyze`

**Analyze uniqueness and consequences.** Version 2; cacheable: no.

Check projected uniqueness, forced values, and source-linked contradictions.

Postcondition: Forced values require refutation of alternatives. Cores are sufficient, not guaranteed minimal; facts remain caller claims.

Limits:

- Shared budget across all checks
- auxiliary variables excluded from projected uniqueness.

Required inputs:

- `model`: PuzzleModel

Optional inputs:

- `assumptions`: array of string
- `backend`: one of `"auto"`, `"z3"`, `"cpsat"`, `"reference"`, default `"auto"`
- `timeout_ms`: integer, default `5000`
- `max_checks`: integer, default `1000`
- `max_assignments`: integer, default `100000`

Output fields: `backend`, `backend_version`, `active_constraint_ids`, `enabled_hypotheses`, `answer_variables`, `stats`, `scope`, `execution_status`, `failed_checks`, `status`, `assignment`, `alternative_assignment`, `uniqueness`, `forced_values`, `not_forced`, `undetermined`, `unsat_core`, `core_minimal`, `core_sources`, `complete`, `reason`.

Example input:

```json
{
  "model": {
    "variables": {
      "x": {
        "lower": 0,
        "upper": 3
      },
      "y": {
        "lower": 0,
        "upper": 3
      }
    },
    "constraints": [
      {
        "id": "sum",
        "expr": {
          "op": "eq",
          "args": [
            {
              "op": "add",
              "args": [
                "x",
                "y"
              ]
            },
            3
          ]
        }
      },
      {
        "id": "order",
        "expr": {
          "op": "lt",
          "args": [
            "y",
            "x"
          ]
        }
      },
      {
        "id": "gap",
        "expr": {
          "op": "eq",
          "args": [
            {
              "op": "sub",
              "args": [
                "x",
                "y"
              ]
            },
            3
          ]
        }
      }
    ]
  },
  "backend": "reference"
}
```

### `symbolic.export`

**Export a reproducible formal model.** Version 1; cacheable: yes.

Export generated SMT-LIB and sanitized symbol/source mappings.

Postcondition: Serialization only; no arbitrary code or raw SMT-LIB is accepted for execution.

Limits:

- Same typed AST and admission limits.

Required inputs:

- `model`: PuzzleModel

Optional inputs:

- `assumptions`: array of string

Output fields: `smt2`, `variable_mapping`, `constraint_mapping`, `scope`.

### `symbolic.inspect`

**Preflight a bounded symbolic model.** Version 1; cacheable: yes.

Return field diagnostics and explicit optional exact integer coefficient reduction before solver admission.

Postcondition: Diagnostics and explicitly requested integer-equivalent rewriting only; no solver execution, inferred bounds or clue interpretation.

Limits:

- 256 variables,1024 rules,20000 AST nodes
- raw integers <=256 bits, normalized intermediate integers <=1024 bits
- output admission bounds remain enforced.

Required inputs:

- `model`: object of JsonValue

Optional inputs:

- `assumptions`: array of string
- `normalize_coefficients`: boolean, default `false`

Output fields: `status`, `valid`, `diagnostics`, `diagnostics_truncated`, `normalized_model`, `input_model_sha256`, `normalized_model_sha256`, `normalization_applied`, `rewrites`, `capabilities`, `domain_examples`, `scope`.

Example input:

```json
{
  "model": {
    "variables": {
      "x": {
        "lower": 0,
        "upper": 3
      }
    },
    "constraints": [
      {
        "id": "clue",
        "expr": {
          "op": "ge",
          "args": [
            {
              "op": "mul",
              "args": [
                4000000000000,
                "x"
              ]
            },
            6000000000001
          ]
        }
      }
    ]
  },
  "normalize_coefficients": true
}
```

### `symbolic.solve`

**Solve symbolic constraints.** Version 2; cacheable: no.

Enumerate projected answers and retain independently checked full witnesses.

Postcondition: Exact witnesses for the formal model. Complete only after enumeration exhaustion; UNKNOWN is not UNSAT.

Limits:

- 256 variables,1024 rules,20000 AST nodes
- time,check,reference-work and output budgets.

Required inputs:

- `model`: PuzzleModel

Optional inputs:

- `assumptions`: array of string
- `backend`: one of `"auto"`, `"z3"`, `"cpsat"`, `"reference"`, default `"auto"`
- `timeout_ms`: integer, default `5000`
- `max_checks`: integer, default `1000`
- `max_assignments`: integer, default `100000`
- `max_solutions`: integer, default `100`

Output fields: `backend`, `backend_version`, `active_constraint_ids`, `enabled_hypotheses`, `answer_variables`, `stats`, `scope`, `execution_status`, `failed_checks`, `status`, `solutions`, `witnesses`, `complete`, `reason`, `unsat_core`, `core_minimal`.

Example input:

```json
{
  "model": {
    "variables": {
      "x": {
        "lower": 0,
        "upper": 3
      },
      "y": {
        "lower": 0,
        "upper": 3
      }
    },
    "constraints": [
      {
        "id": "sum",
        "expr": {
          "op": "eq",
          "args": [
            {
              "op": "add",
              "args": [
                "x",
                "y"
              ]
            },
            3
          ]
        }
      }
    ]
  },
  "backend": "reference"
}
```

### `symbolic.verify`

**Independently check an assignment.** Version 1; cacheable: yes.

Evaluate every active constraint using a separate pure-Python interpreter.

Postcondition: Checks execution against the same formal model, not independent interpretation of the original clue.

Limits:

- Requires a complete assignment
- strict sorts and domains.

Required inputs:

- `model`: PuzzleModel
- `assignment`: object of integer or boolean

Optional inputs:

- `assumptions`: array of string

Output fields: `valid`, `violated_domains`, `violated_constraints`, `checked_constraint_ids`, `scope`.

## text

### `text.encode`

**Encode text as exact bytes.** Version 1; cacheable: yes.

Choose ascii, utf-8, or latin-1 explicitly; keep the byte span of each code point.

Postcondition: Exact encoding under the specified codec; no normalization or error repair.

Limits:

- 16384 source code points and encoded bytes
- errors are rejected, never replaced.

Required inputs:

- `text`: string
- `codec`: one of `"ascii"`, `"utf-8"`, `"latin-1"`

Output fields: `hex`, `byte_length`, `codepoint_length`, `codepoint_byte_spans`, `codec`, `scope`.

Example input:

```json
{
  "text": "A雪",
  "codec": "utf-8"
}
```

### `text.profile`

**Describe a symbol stream.** Version 1; cacheable: yes.

Return codepoint counts, empirical entropy, coincidence and grid dimensions.

Postcondition: Exact counts/dimensions; floating descriptive statistics. No interpretation is inferred.

Limits:

- 65536 codepoints.

Required inputs:

- `text`: string

Output fields: `codepoint_length`, `utf8_byte_length`, `alphabet_size`, `counts`, `index_of_coincidence`, `empirical_entropy_bits`, `rectangular_dimensions`, `interpretation`.

Example input:

```json
{
  "text": "ATTACKATDAWN"
}
```

### `text.symbol_map`

**Map symbols without silent deletion.** Version 1; cacheable: yes.

Postcondition: Exact supplied transformation; not evidence of the intended puzzle mechanism.

Limits:

- Bounded text, explicit alphabets and normalization
- inspect input schema.

Required inputs:

- `text`: string
- `mapping`: object of string

Output fields: `text`, `source_offsets`, `dropped_offsets`, `source_length`, `scope`.

Example input:

```json
{
  "text": "a b",
  "mapping": {
    "a": "0",
    " ": "",
    "b": "1"
  }
}
```

## utility

### `utility.compare_runs`

**Compare matched agent investigation runs.** Version 1; cacheable: yes.

Recompute answer correctness; account for missing runs, missing costs and false claims before comparing paired latency.

Postcondition: Scoring supplied episodes only, not executing models or validating target provenance.

Limits:

- 200 tasks,3 conditions,600 episodes
- exact-byte answer bounds.

Required inputs:

- `tasks`: array of Task
- `conditions`: array of string
- `model_id`: string
- `budget`: Budget
- `episodes`: array of Episode

Output fields: `conditions`, `paired`, `metrics_are_runner_reported`, `scope`.

## verify

### `verify.sha256`

**Check a byte commitment.** Version 1; cacheable: yes.

Compare exact candidate bytes against a supplied SHA256 commitment.

Postcondition: Digest equality under the provided commitment. Commitment provenance is not authenticated.

Limits:

- 65536 candidate bytes.

Required inputs:

- `candidate_hex`: string
- `expected_sha256`: string

Output fields: `match`, `observed_sha256`, `expected_sha256`, `evidence_kind`, `scope`.

Example input:

```json
{
  "candidate_hex": "616263",
  "expected_sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
}
```
