# Agent setup

Repository instructions and a tool connection are separate. This checkout
provides both: instruction files for coding agents, and a local MCP server. It
does not change your global agent configuration or grant network access.

## Instruction files

- `AGENTS.md` is the canonical maintainer guide.
- `polya/AGENTS.md` adds runtime rules; `tests/AGENTS.md` adds test rules;
  `native/AGENTS.md` covers the Rust experiment.
- `CLAUDE.md` imports the root guide. `.github/copilot-instructions.md` points to it.
- `.github/pull_request_template.md` asks for verification, counterarguments and
  limitations.

## Investigation skill

The skill is `polya/SKILL.md` in two host directories: `.agents/skills/` (Codex)
and `.claude/skills/` (Claude Code). The two files must stay byte-identical: edit
one and copy it over the other.
`tests/test_agent_discovery.py` fails if they differ or if a link in them does not
resolve. Their description limits them to puzzle investigations, not repository
edits. Host support, settings and workspace trust decide whether a host loads them.

```bash
python -m pytest -q tests/test_agent_setup.py tests/test_agent_discovery.py
```

## Connect the tool

Install Polya ([getting started](../getting-started.md)), check backends, and start
the server:

```bash
python -m polya run backends.inspect --json '{}'
python -m polya mcp
```

Configure the host to run the installed environment's Python with arguments
`-m polya mcp`; see [MCP](mcp.md). Then follow [investigating](investigating.md).

When checking a client, confirm which instructions and skills it loaded, and run a
small known-answer operation before a real investigation.

## Scope and limits

The tests check file layout and links. They do not show that a given client
release loaded the skill. Client behavior changes; check the host's documentation:
[Codex skills](https://developers.openai.com/codex/skills),
[Claude Code skills](https://code.claude.com/docs/en/skills),
[Claude Code memory and imports](https://code.claude.com/docs/en/memory).
