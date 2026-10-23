# Method integration validation, 17 October 2026

## Revision and scope

The base is upstream `b6f023736c27d35b1327b8e0b78648633367c4ce`, tree
`f2fb49052c36df300b621fad94e658972802c375`. All 169 base files were checked
against their Git blob identities before editing; the reconstructed tree matched.
Older working copies were not modified. This record covers the method integration
diff, not previously reported prototype results or a model-efficacy experiment.

Only `method.retrieve` is a new registry operation. It uses six fixed educational
references without network access or caller-selected paths. Archive access and
gold scoring are offline controller/evaluator APIs. Private research artifacts,
account data and puzzle-specific operational workflows are not included.

## Checks executed

On CPython 3.12.14 / Linux:

- `python -m pytest -q -rs`: **1274 passed, 42 skipped, 241 subtests passed**;
  two existing dependency-deprecation warnings. The earlier full run had one
  inventory failure, because the deliberately added operation changed 53 to 54.
  The exact-count assertion was updated with an explicit `method.retrieve`
  membership check, then the full suite was rerun successfully.
- `python -m pytest -q tests/test_method_learning.py
  tests/test_method_integrity_review.py tests/test_method_integration.py`:
  **54 passed**, independently reproduced by a separate reviewer.
- `python -m pytest -q tests/test_agent_setup.py tests/test_agent_discovery.py`:
  **8 passed** after final documentation edits.
- `python scripts/verify_method_examples.py`: all **six original development
  fixtures** and the collection check passed. Exhaustive small-grid/tiling/trail
  checks are independent of the lexical retriever; they are not model trials.
- Generated operation reference check, compileall, `pip check`, `polya doctor`,
  structured demo and `git diff --check`: passed.
- Wheel built with `pip wheel --no-build-isolation --no-deps`. Its three method
  data files, module bytes and absence of bytecode were checked. An isolated
  interpreter imported the extracted wheel and exercised retrieval and legacy
  nested-module identity, outside the source checkout's import path.
- The existing installed-wheel CI job now exercises bundled retrieval data.
  Remote CI is separate evidence and must be checked on the exact published head.

Environment: Pydantic 2.14.1, cryptography 50.0.2, pytest 9.1.1, jsonschema 4.26.0,
Z3 4.16.0.0, OR-Tools 9.15.6755, AALpy 1.6.2, Pillow 12.3.0. Dependencies already
available locally were reused in a separate environment; no external model or
paid computation was invoked.

## Skips and untested boundaries

The 42 skips consist of 35 optional compiled-Rust cases; one separately installed
Jacobian integration; one legacy-Z3-version job; three real Python 3.15 or
free-threaded runtime cases; and two absent-backend branches that are inapplicable
because AALpy and CP-SAT are installed (their positive integrations ran).
Windows archive behavior was reviewed but not executed locally. Real Python
3.11/3.13/3.14/3.15, free-threaded and platform-matrix execution remain CI evidence,
not simulated local passes. Missing checks are not successes.

## Independently reviewed repairs

The reviewer supplied eight failing prototype regressions before integration.
The integration fixes every-manifest schema/type checks and shared intervention
fingerprints; mutable retrieval aliases; double-serialization archive races;
oversized integer counters; non-string skill inputs; bounded strict file reads;
JSON float overflow and schema whitespace/end-of-ID mismatches. Additional checks
cover binary reference fingerprints, nested package/data receipt fingerprints,
Python-only JSON coercions, malformed inputs, registry/CLI/MCP parity, concurrent
duplicate publication and nested compatibility-module identity.

Post-publication review identified an aggregate fresh-packet size gap despite
per-record archive bounds. Four new size-limit cases failed on the initial code.
The correction caps problem/scope text and validates the complete canonical
UTF-8 packet before reading evidence, then incrementally after each selected
record. Six added cases cover inclusive text and exact 2,000,000-byte boundaries,
one-byte overflow, multibyte text, lone surrogates, metadata overhead and stopping
before further reads. Independent review reproduced all 54 method tests and
additional Unicode/escaping probes. The subsequent full run above passed in
94.98 seconds; the initial published revision had passed 1268 tests locally.

The archive is append-only through its API and tamper-evident, not protected from
a same-user writer. Reported usage is not independent metering. The development
library is not a hidden benchmark or an unrestricted training corpus. No paired
held-out model trial, training, open-puzzle solve or solving improvement is claimed.
