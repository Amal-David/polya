"""Regression checks for discoverable, synchronized agent instructions."""
from pathlib import Path
import importlib.util
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("polya_skill_sync", ROOT / "scripts/sync_agent_skills.py")
assert SPEC is not None and SPEC.loader is not None
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)


def test_host_skills_match_the_canonical_instructions():
    assert SYNC.sync(ROOT, check=True) == []
    canonical = (ROOT / "skills/polya/SKILL.md").read_text(encoding="utf-8")
    assert canonical.startswith("---\nname: polya\ndescription: ")
    assert "UNKNOWN" in canonical and "held-out evidence" in canonical


def test_host_skill_links_resolve_inside_checkout():
    for relative in SYNC.DESTINATIONS:
        path = ROOT / relative
        for link in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            target = (path.parent / link).resolve()
            assert target.is_relative_to(ROOT.resolve()), link
            assert target.is_file(), (relative, link)


def test_check_mode_detects_missing_entries_without_writing(tmp_path):
    source = tmp_path / "skills/polya/SKILL.md"
    source.parent.mkdir(parents=True)
    source.write_text("canonical", encoding="utf-8")
    assert SYNC.sync(tmp_path, check=True) == list(SYNC.DESTINATIONS)
    assert not (tmp_path / ".agents").exists()
    assert not (tmp_path / ".claude").exists()


def test_generation_rewrites_links_and_is_idempotent(tmp_path):
    source = tmp_path / "skills/polya/SKILL.md"
    source.parent.mkdir(parents=True)
    source.write_text("[guide](../../docs/AGENT-USAGE.md)", encoding="utf-8")
    assert SYNC.sync(tmp_path, check=False) == list(SYNC.DESTINATIONS)
    assert SYNC.sync(tmp_path, check=False) == []
    for relative in SYNC.DESTINATIONS:
        assert "(../../../docs/" in (tmp_path / relative).read_text(encoding="utf-8")


def test_check_detects_drift_and_generation_repairs_it(tmp_path):
    source = tmp_path / "skills/polya/SKILL.md"
    source.parent.mkdir(parents=True)
    source.write_text("canonical", encoding="utf-8")
    SYNC.sync(tmp_path, check=False)
    target = tmp_path / SYNC.DESTINATIONS[0]
    target.write_text("outdated", encoding="utf-8")
    assert SYNC.sync(tmp_path, check=True) == [SYNC.DESTINATIONS[0]]
    assert target.read_text(encoding="utf-8") == "outdated"
    assert SYNC.sync(tmp_path, check=False) == [SYNC.DESTINATIONS[0]]
    assert SYNC.sync(tmp_path, check=True) == []


def test_sync_cli_check_succeeds():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/sync_agent_skills.py"), "--check"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
