# Native experiments

Read ../AGENTS.md and README.md before editing. This is an opt-in benchmark kernel,
not a second implementation of the library or a default solver. No puzzle controls
native library paths, exported symbol names, imports, or executable code.

Keep bounds and UNKNOWN outcomes. Compare native results with both the matched
Python algorithm and the independent original comparator; replay witnesses with
the original simulator. Test domain errors and depth/pair/time/output budgets.
Measure conversions, model preparation, and checking as well as kernel time.
Never equate benchmark throughput with improved agent reasoning. Keep binaries
out of Git and require actual native execution in the experiment CI job.
