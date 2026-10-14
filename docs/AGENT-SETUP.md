# Agent setup

Repository instructions and a tool connection are different things. This checkout
provides both instructions and a local MCP server; it does not modify your global
agent configuration or grant network access.

## Maintainer instructions

- `AGENTS.md` is the canonical repository policy: broad puzzle coverage, public
  contracts, exact commands, compatibility, adversarial review and independent checks.
- `polya/AGENTS.md` adds runtime rules; `tests/AGENTS.md` adds test requirements.
- `CLAUDE.md` imports the root guide. Copilot's repository instructions refer to it.
- The pull-request template asks for verification, counterarguments and limitations.

## Investigation skill

The skill is `.agents/skills/polya/SKILL.md` (Codex) and `.claude/skills/polya/SKILL.md`
(Claude Code). The two files must stay byte-identical: edit both together.
`tests/test_agent_discovery.py` fails if they differ or if a link in them does not
resolve to a file in the checkout. Their descriptions scope them to using Polya for
puzzle experiments, not ordinary repository edits. Host support, enabled settings
and workspace trust still determine loading. The tests validate file layout and
links; they do not certify that every client release has loaded the skill.

```bash
python -m pytest -q tests/test_agent_setup.py tests/test_agent_discovery.py
```

## Connect the tool separately

Install from this checkout and inspect actual backend availability:

```bash
python -m pip install -e '.[test,solvers,learning]'
python -m polya run backends.inspect --json '{}'
python -m polya mcp
```

Configure your host to start the installed environment's Python executable with
arguments `-m polya mcp`; see [MCP setup](MCP.md). Discover with `puzzle.find`, inspect
one exact contract, and execute with `puzzle.run`. Treat missing integrations,
unknown results and budget limits explicitly. See [investigation rules](AGENT-USAGE.md).

When checking a client, confirm which instructions/skills it actually loaded and
run a small known-answer operation before beginning a real investigation.

## References

Client behavior can change; check the host's documentation rather than guessing:
- [OpenAI Codex skills](https://developers.openai.com/codex/skills)
- [Claude Code skills](https://code.claude.com/docs/en/skills)
- [Claude Code memory and imports](https://code.claude.com/docs/en/memory)

## Native solver compatibility

The supported Z3 range is >=4.13,<5, matching the package metadata. An older
system libz3 (including 4.8.12) is rejected before context creation and reports
UNAVAILABLE, rather than crashing during SMT-LIB initialization or pretending
to solve. The reference backend remains available explicitly. The legacy CI
job tests this rejection contract; it does not certify legacy solving support.
