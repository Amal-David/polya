# Third-party references

The implementation was written for this prototype. No upstream Jacobian or
open-crypto-puzzles source code, CUDA engines, puzzle images, books, or other
challenge media are bundled.

- Conceptual inspiration: morluto, [Jacobian](https://github.com/morluto/jacobian)
  and [AI Math, Paul Erdos & Attention](https://morluto.bearblog.dev/ai-math-paul-erdos-and-attention/).
- Research corpus: floflo777, [open-crypto-puzzles](https://github.com/floflo777/open-crypto-puzzles),
  inspected at commit `7f691a58c2c6ac60b0d7fd369376f91b48f27cb3`.
  Any adapted catalogue metadata is attributed to floflo777 under
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), separately from
  this implementation's MIT license. Puzzle assets retain their own rights.
  Coverage notes describe a historical research input, not current prize status.
- BIP39 seed semantics and the one public English calibration vector:
  [BIP-0039](https://github.com/bitcoin/bips/blob/master/bip-0039.mediawiki) and
  [Trezor vectors](https://github.com/trezor/python-mnemonic/blob/master/vectors.json).
  Both projects are MIT licensed. No wallet owned by a third party is used.
- EVP_BytesToKey semantics: [OpenSSL documentation](https://docs.openssl.org/3.0/man3/EVP_BytesToKey/).
  Synthetic crypto fixtures were produced by the OpenSSL CLI. This independently
  checks the KDF/framing code, not every low-level cipher primitive: cryptography
  may also use OpenSSL internally for AES.
- The native bridge uses the documented [Z3 C API](https://z3prover.github.io/api/html/group__capi.html).
  Optional adapters use [OR-Tools](https://developers.google.com/optimization/cp)
  and [AALpy](https://github.com/DES-Lab/AALpy); dependencies are not vendored.
- The native learner implements a Mealy observation-table approach. Finite
  conformance tests do not provide the full equivalence-oracle assumptions of
  classical active learning.
- The stdio transport implements a subset of the
  [MCP 2025-06-18 specification](https://modelcontextprotocol.io/specification/2025-06-18/server/tools).
  No MCP SDK source is included.

Pydantic, cryptography, optional solvers and their dependencies retain their
respective licenses. No dependency distributions are bundled in this source tree.

# Educational method references

The method library at `polya/methods/data/` contains independently written
descriptions and original toy fixtures with links to source readings. It does not
bundle source books, prose, code or figures. Its per-record `license_basis` and
`SOURCE-NOTES.md` retain source-specific restrictions, including CC BY-NC-SA 4.0
and jurisdiction-specific public-domain status. The repository license does not
grant rights in the linked sources or make them a cleared training corpus.
