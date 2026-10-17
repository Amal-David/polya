# Local helper entry points

The portable bundle contains `polya/methods/`, its packaged data, and this skill. Run from an installed Polya checkout (Python 3.11+); copying only SKILL.md preserves guidance but does not install helper modules or examples.

```python
from polya.methods.library import load_library, retrieve
from polya.methods.reset import Archive
from polya.methods.evaluation import Budget, make_manifests, check_equal_budget, build_context

examples = load_library('polya/methods/data/examples.json')
references = retrieve(examples, 'parity checkerboard invariant', limit=2)
```

Retrieval returns data-only envelopes with example, matched_terms, score and scope. It matches exact lowercase lexical terms in methods/applicability, not embeddings or solver outcomes. No match returns an empty list; it does not prove no method applies. The actual example schema is `polya/methods/data/example.schema.json`; `Example.parse` enforces exact fields and runtime bounds.

```python
archive = Archive('/path/owned-by-controller/evidence')
experiment = {'method': 'color-balance', 'inputs': {'board': 'toy'},
              'budget': {'tool_calls': 1}, 'version': '1'}
attempt_id, already_attempted = archive.record_attempt(experiment)
# Controller executes only if not already_attempted, and checks its result independently.
# record_verified(claim, receipt, checker) is an attestation API, not an automatic checker.
packet = archive.fresh_packet('Original toy puzzle', evidence_ids=[],
                              remaining_budget={'tool_calls': 7},
                              scope='Educational puzzle; local checks only.')
```

Archive publication uses atomic hard links on a local supporting filesystem and detects byte/hash corruption. It is not hardened against a same-user adversary or power-loss recovery. Deployment must deny proposer access to controller storage, and persist/enforce the global budget outside the packet.

Evaluation functions live in `polya.methods.evaluation`. `build_context` exposes only id/problem plus the arm's allowed skill and validated retrieval envelopes. Schema checks cannot detect a hidden answer embedded as text inside an otherwise valid reference; retrieval must be from a frozen, independently curated development library. Golds and scorer access remain evaluator-only. Read evaluation.md before using the harness for claims.
