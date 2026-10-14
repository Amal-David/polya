"""The two host skill copies are one skill and must stay identical."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST_SKILLS = (".agents/skills/polya/SKILL.md", ".claude/skills/polya/SKILL.md")


def test_host_skills_are_identical():
    codex, claude = ((ROOT / relative).read_bytes() for relative in HOST_SKILLS)
    assert codex == claude, "edit both host skill copies together"
    # Windows checkouts may carry CRLF line endings.
    assert codex.decode("utf-8").replace("\r\n", "\n").startswith("---\nname: polya\ndescription: ")
