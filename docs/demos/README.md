# CLI recordings

These are real terminal sessions with synthetic inputs. No output is mocked or
edited. All three examples work with the base Polya install, without optional
solvers, credentials or network calls. `--result-only` omits the execution receipt.

## Try the examples

Find a cipher operation and inspect its example input:

```bash
polya find vigenere --limit 1
polya inspect cipher.polyalphabetic --example
```

Decode a supplied Vigenere ciphertext with a known key:

```bash
polya run cipher.polyalphabetic --result-only \
  --json '{"text":"LXFOPVEFRNHR","key":"LEMON","variant":"vigenere"}'
```

The returned `text` is `ATTACKATDAWN`. This checks the supplied transformation;
it does not establish an unknown puzzle's mechanism.

Enumerate two binary variables constrained to have different values:

```bash
polya run constraints.solve --result-only \
  --json '{"domains":{"a":["0","1"],"b":["0","1"]},
"constraints":[{"scope":["a","b"],"allowed":[["0","1"],["1","0"]]}]}'
```

The two solutions are `{"a":"0","b":"1"}` and `{"a":"1","b":"0"}`.
`status: COMPLETE` and `termination_reason: exhausted` apply only to these
declared domains and allowed tuples.

## Re-record

Install [VHS](https://github.com/charmbracelet/vhs), including its FFmpeg and ttyd
dependencies, and the [JetBrains Mono](https://www.jetbrains.com/lp/mono/) font.
The checked-in recordings use VHS 0.11.0 at 1100 × 780 pixels.

From the repository root, create a local environment and install Polya:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Validate the tapes, then regenerate the GIFs:

```bash
vhs validate 'docs/demos/*.tape'
vhs docs/demos/discovery.tape
vhs docs/demos/cipher.tape
vhs docs/demos/constraints.tape
```

Each tape runs Polya in Bash. `terminal.tape` supplies the shared appearance and
activates `.venv`; it hides only terminal setup. The commands and their complete
result objects remain visible. Review the animations after regeneration to check
that inputs, outputs and scope statements fit on screen.
