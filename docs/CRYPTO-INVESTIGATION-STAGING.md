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
