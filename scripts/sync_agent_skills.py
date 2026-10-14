"""Generate host skill entry points from one canonical, versioned skill."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

DESTINATIONS = (
    ".agents/skills/polya/SKILL.md",
    ".claude/skills/polya/SKILL.md",
)


def sync(root: Path, *, check: bool) -> list[str]:
    """Return stale paths; check mode never writes to the checkout."""
    source = (root / "skills/polya/SKILL.md").read_text(encoding="utf-8")
    rendered = source.replace("(../../docs/", "(../../../docs/")
    stale: list[str] = []
    for relative in DESTINATIONS:
        path = root / relative
        if path.is_file() and path.read_text(encoding="utf-8") == rendered:
            continue
        stale.append(relative)
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(rendered, encoding="utf-8")
    return stale


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify without writing")
    args = parser.parse_args()
    try:
        stale = sync(Path(__file__).resolve().parents[1], check=args.check)
    except (OSError, UnicodeError) as exc:
        print(f"Skill synchronization failed: {exc}", file=sys.stderr)
        return 2
    if stale and args.check:
        print("Stale skill entries: " + ", ".join(stale), file=sys.stderr)
        print("Run python scripts/sync_agent_skills.py", file=sys.stderr)
        return 1
    print("Skill entry points are in sync.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
