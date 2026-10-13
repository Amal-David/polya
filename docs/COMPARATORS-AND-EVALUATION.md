# Comparators and evaluation

Relevant primary projects include [Jacobian](https://github.com/morluto/jacobian),
[CyberChef](https://github.com/gchq/CyberChef), [Chepy](https://github.com/securisec/chepy),
[Ciphey](https://github.com/bee-san/Ciphey), [Z3](https://github.com/Z3Prover/z3),
[OR-Tools](https://github.com/google/or-tools), and [AALpy](https://github.com/DES-Lab/AALpy).
Pin versions and inspect actual supported interfaces before integrating; these
references are not vendored implementations or claims of outperformance.

The differentiator to evaluate is a shared vocabulary of exact representations,
explicit assumptions, composable operations, bounded searches and scoped results.
A long list of decoder functions or an MCP wrapper alone does not establish this.

## Controlled comparisons

Compare the same reasoning model and underlying algorithms with:

1. Ordinary Python plus existing tools.
2. The same capabilities exposed through Polya's contracts.
3. Polya plus a separately evaluated persistent investigation layer.

Keep hardware and budgets equal. Report model-construction time, backend time,
verification, serialization, cold start, warm throughput, token use, and verified
success. A Rust port must be compared with the same algorithm, not credited for
an unrelated change from exhaustive search to constraint propagation.

Use family-stratified held-outs, fresh generated instances, and deliberately
misleading controls. Public historical solutions risk memorization. Real open
puzzles belong in a separate prospective log, with independently verified stage
progress distinguished from final acceptance.

The exhaustive reference here is a correctness baseline, not a competitive
specialized solver. Unit-test duration and tiny synthetic demonstrations are
not agent-efficiency benchmarks. See [validation](../validation/POLYA-MIGRATION.md).
