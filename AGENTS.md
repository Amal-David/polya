# Using Polya as a puzzle-solving agent

Start with `puzzle.find`, inspect a promising operation's exact contract, then
run it. Reuse the original primitives where appropriate; do not turn every
puzzle into a SAT problem or a hidden-state learning problem.

Preserve observations separately from interpretations. Source every rule when
possible. Mark speculative rules as hypotheses and activate them explicitly.
A contradiction is a contradiction in the supplied model, not a refutation of
an author's possible intent. Revisit extraction and translation when appropriate.

Choose answer variables deliberately. Auxiliary solver variables do not make
an answer ambiguous. Do not claim uniqueness from seeing only one result on a
truncated page; use `symbolic.analyze` and inspect its uniqueness status.

Use `symbolic.verify` or an independent domain checker on witnesses. Cross-
backend agreement does not independently validate the same mistranslated clue.
Use actual unused evidence or a separate interpretation route for that task.

Before requesting more guesses, compare the consequences of explicit models.
`hypotheses.compare` identifies conflicting forced observations;
`automata.distinguish` finds a shortest separating input between supplied
machines. These propose experiments and do not perform external observations.

Only learn automata when resettable, repeatable behavior and an informative
alphabet are available. The tools learn from supplied local simulators. Use the
Python reset/step interface only for authorized systems and account for every
query/reset. A lone opaque checker is not automatically an informative teacher.

Read status and scope together. UNKNOWN, UNAVAILABLE, UNSUPPORTED, and budget
exhaustion are not UNSAT. BOUNDED_CONFORMANCE is not global equivalence.
No independent validation is established by a cache hit. No tool call can
establish the absence of missing external evidence.

Keep searches bounded and preserve negative scopes. Do not mutate an external
service, transact with a wallet, or execute untrusted puzzle code through an
invented tool. No such endpoints exist in this server.

When proposing a new operation, demonstrate reuse across unrelated mechanism
families and include a known positive, relevant negatives, and an independently
implemented check. Do not give any named puzzle a privileged architecture role.
