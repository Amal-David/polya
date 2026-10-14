> Historical record. Operation IDs and paths may be stale.

# Crypto-investigation changes — publication staging

This is a **draft**, intentionally not merge-ready. The reviewed full 26-file implementation was
prepared against main `3b7561087b677a4048d4f2495ebdc2462b9fd8c6` and its original
Git tree `31ec22241fc51f3f190009498744ab893cb77c83`.

This branch currently contains only the first independently testable component:
specialist-proposal verification, with regression tests. The complete reviewed
patch also adds casepack inspection and replay, text extraction, mechanism synthesis,
PNG-bit search, historical cases, agent instructions, and tests.

The complete patch SHA-256 is
`ba0b67e44ec1e573cb21d7165c7389becee14eca1ec74841b48bfaf29b28cb34`.
The full reviewed result would have Git tree
`c5e09ec24ddca8f2d920ff37e630f939bec132fc`.

**Do not merge this draft as the complete implementation.** The rest of the
reviewed patch must be applied, the resulting tree checked, and fresh CI run.
No new puzzle solution or 10x agent-performance gain is claimed.

## Published specialist-verification contract

`specialist.verify_proposal` returns exactly one of `REJECTED`,
`CHECKPOINT_MATCH`, or `MECHANISM_CONSISTENT_ONLY`. Every result retains the
supplied `expected_plaintext_sha256` and `checkpoint_source` (both `null` when
no checkpoint is supplied). Source labels are caller-supplied and unauthenticated;
a matching commitment does not establish that its source is externally published.

`artifact_sha256` hashes the exact ciphertext string, and `plaintext_sha256` and
`expected_plaintext_sha256` refer to the exact plaintext string. In each case the
byte representation is UTF-8, without normalization or an added byte-order mark,
as reported by `digest_encoding: "utf-8"`. These are not digests of original
artifact files, alternative encodings, or JSON serialization. Existing digest
semantics are unchanged. The additional result fields and finite status schema
clarify this pre-stable operation without renaming it or removing existing fields.

These review corrections apply only to the published first slice. The original
full-patch hash and tree above remain the identity of the prior reviewed artifact,
not the expected tree after these corrections; the remaining transfer and fresh
full-implementation validation are still required.
