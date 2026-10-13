# Maintaining agent skills

Read [the root guide](../AGENTS.md). `skills/polya/SKILL.md` is the canonical
investigation skill. Host copies in `.agents/skills/polya/` and
`.claude/skills/polya/` are generated, not separate policies.

After changing the canonical skill, run:

```bash
python scripts/sync_agent_skills.py
python scripts/sync_agent_skills.py --check
python -m pytest -q tests/test_agent_setup.py tests/test_agent_discovery.py
```

Preserve explicit applicability, known limitations, bounded-result semantics,
source provenance, adversarial review, and independent verification. Skill text
must not imply that dependencies, MCP registration, global client configuration,
or external permissions have been installed. See [agent setup](../docs/AGENT-SETUP.md).
