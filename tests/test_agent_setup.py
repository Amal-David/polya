"""Keep agent entry points, documentation links and diagnostic commands usable."""
from pathlib import Path
import importlib.util
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_agent_entrypoints_share_the_root_guide():
    assert "@AGENTS.md" in (ROOT / "CLAUDE.md").read_text()
    assert "../AGENTS.md" in (ROOT / ".github/copilot-instructions.md").read_text()
    for path in ("polya/AGENTS.md", "tests/AGENTS.md", ".claude/skills/polya/SKILL.md",
                 "docs/agents/investigating.md", "docs/internals/performance.md"):
        assert (ROOT / path).is_file(), path


def test_documentation_links_resolve_inside_the_repository():
    files = [ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "CONTRIBUTING.md",
             ROOT / "polya/AGENTS.md", ROOT / "tests/AGENTS.md",
             ROOT / ".github/copilot-instructions.md",
             ROOT / ".agents/skills/polya/SKILL.md", ROOT / ".claude/skills/polya/SKILL.md",
             *sorted((ROOT / "examples").rglob("README.md")),
             *sorted((ROOT / "docs").rglob("*.md"))]
    for path in files:
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
            if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
                continue
            relative = target.split("#", 1)[0]
            resolved = (path.parent / relative).resolve()
            assert resolved.is_relative_to(ROOT.resolve()), (path, target)
            assert resolved.exists(), (path, target)


def test_package_version_matches_distribution_metadata():
    import polya
    from importlib import metadata
    assert polya.__version__ == metadata.version("polya-puzzles")


def test_operation_reference_matches_the_registry():
    spec = importlib.util.spec_from_file_location(
        "generate_operations_doc", ROOT / "scripts/generate_operations_doc.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    committed = (ROOT / "docs/operations.md").read_text(encoding="utf-8")
    assert committed == generator.generate(), "run python scripts/generate_operations_doc.py"


def test_documented_cli_operation_executes():
    command = [sys.executable, "-m", "polya", "run", "bytes.decode", "--json",
               '{"encoding":"hex","value":"41"}']
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["result"]["hex"] == "41"


def test_benchmark_cli_rejects_unbounded_repeats():
    result = subprocess.run([sys.executable, str(ROOT / "scripts/benchmark_operations.py"),
                             "--repeats", "0"], capture_output=True, text=True, timeout=20)
    assert result.returncode == 2


def test_benchmark_reports_scope_and_actual_results():
    result = subprocess.run([sys.executable, str(ROOT / "scripts/benchmark_operations.py"),
                             "--repeats", "1"], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert len(data["workloads"]) == 4
    assert all(len(row["public_api"]["samples_ms"]) == 1 for row in data["workloads"])
    assert "No Rust implementation" in data["limits"]
