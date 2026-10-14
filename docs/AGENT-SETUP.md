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

The canonical source is `skills/polya/SKILL.md`. Checked-in host entry points are
`.agents/skills/polya/SKILL.md` and `.claude/skills/polya/SKILL.md`. Their descriptions
scope them to using Polya for puzzle experiments, not ordinary repository edits.
Host support, enabled settings and workspace trust still determine loading.
The repository tests validate file layout, links and synchronization; they are
not a certification that every client release has loaded the skill.

After editing the canonical skill, regenerate and verify the host copies:

```bash
python scripts/sync_agent_skills.py
python scripts/sync_agent_skills.py --check
python -m pytest -q tests/test_agent_setup.py tests/test_agent_discovery.py
```

Do not edit the generated host copies independently. Their relative documentation
links are adjusted for the extra directory level. CI fails if they drift.

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
