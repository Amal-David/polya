# GSMG case files

Replay fixtures from the public GSMG.IO puzzle: its published phase-2 decryption control (`gsmg-phase2-control.json`), a SalPhaseIon candidate profile (`gsmg_gate.py`), and published checkpoint transcriptions, including one Kryptos K1 calibration (`cryptic-checkpoints.json`).
Provenance (upstream repositories, commit and blob IDs, representation changes) is recorded inside each JSON file.
These are replay and calibration fixtures, not a solver: they reproduce published stages and do not recover the final GSMG password.
Run `python -m examples.cases.gsmg.gsmg_gate --candidates candidates.json` to test your own candidates; see [plans](../../../docs/guides/plans.md#testing-candidates-against-the-gsmg-salphaseion-lock) for its scope.
`examples.cryptic_demo` and `examples.crypto_frontier_demo` read these files.
