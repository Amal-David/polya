"""The two host skill copies are one skill and must stay identical."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HOST_SKILLS = (".agents/skills/polya/SKILL.md", ".claude/skills/polya/SKILL.md")


def test_host_skills_are_identical_and_their_links_resolve():
    codex, claude = ((ROOT / relative).read_bytes() for relative in HOST_SKILLS)
    assert codex == claude, "edit both host skill copies together"
    text = codex.decode("utf-8")
    assert text.startswith("---\nname: polya\ndescription: ")
    for relative in HOST_SKILLS:
        path = ROOT / relative
        for link in re.findall(r"\]\(([^)]+)\)", text):
            target = (path.parent / link.split("#", 1)[0]).resolve()
            assert target.is_relative_to(ROOT.resolve()), (relative, link)
            assert target.is_file(), (relative, link)
