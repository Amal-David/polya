"""Reviewable weekly upstream-source snapshot, never a blind runtime upgrade.

Writes only the reviewed pin's *observed* upstream fields. The independently
installed runtime stays pinned to its tested release until a reviewer upgrades
it and the cross-interpreter integration job passes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "polya" / "jacobian_pin.json"
GITHUB = "https://api.github.com/repos/morluto/jacobian/git/ref/heads/main"
PYPI = "https://pypi.org/pypi/jacobian/json"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")


def _fetch(url: str):
    # These addresses are constants, not derived from untrusted upstream input.
    request = Request(url, headers={"User-Agent":"polya-jacobian-release-sync/1",
                                     "Accept":"application/json"})
    with urlopen(request, timeout=20) as response:
        raw = response.read(2_000_001)
    if len(raw)>2_000_000:
        raise ValueError("Upstream metadata exceeds two megabytes")
    return json.loads(raw)


def snapshot(current: dict, github: dict, pypi: dict) -> dict:
    if current.get("upstream") != "morluto/jacobian":
        raise ValueError("Unexpected upstream repository")
    sha = github.get("object", {}).get("sha")
    if not isinstance(sha,str) or not SHA40.fullmatch(sha):
        raise ValueError("Invalid upstream main source revision")
    version = pypi.get("info", {}).get("version")
    if not isinstance(version,str) or not re.fullmatch(r"\d+\.\d+\.\d+",version):
        raise ValueError("Upstream latest release version is not stable semantic version")
    if pypi.get("info", {}).get("name", "").lower() != "jacobian":
        raise ValueError("Unexpected package name")
    files = [f for f in pypi.get("urls", []) if f.get("packagetype") == "bdist_wheel"
             and f.get("filename") == f"jacobian-{version}-py3-none-any.whl"]
    if len(files) != 1:
        raise ValueError("Latest version has no unique expected wheel; human review required")
    wheel_hash = files[0].get("digests", {}).get("sha256")
    if not isinstance(wheel_hash,str) or not re.fullmatch(r"[a-f0-9]{64}",wheel_hash):
        raise ValueError("Unexpected wheel SHA256")
    updated = dict(current)
    updated["upstream_main_sha"] = sha
    updated["latest_available_version"] = version
    updated["latest_available_wheel_sha256"] = wheel_hash
    updated["latest_requires_python"] = str(pypi.get("info",{}).get("requires_python") or "unknown")
    # The executable version/source SHA remain unchanged: those refer to the
    # tested, separately installed wheel, not the current HEAD of main.
    return updated


def main(argv=None) -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Update observed upstream fields; never bump the installed runtime pin")
    parser.add_argument("--github-json",type=Path, help="Offline test fixture")
    parser.add_argument("--pypi-json",type=Path, help="Offline test fixture")
    parser.add_argument("--manifest",type=Path,default=MANIFEST)
    args=parser.parse_args(argv)
    if (args.github_json is None) != (args.pypi_json is None):
        parser.error("both offline fixtures must be provided together")
    current=json.loads(args.manifest.read_text(encoding="utf8"))
    if args.github_json:
        github=json.loads(args.github_json.read_text(encoding="utf8"))
        pypi=json.loads(args.pypi_json.read_text(encoding="utf8"))
    else:
        github=_fetch(GITHUB); pypi=_fetch(PYPI)
    new=snapshot(current,github,pypi)
    changed=sorted(k for k in new if new[k]!=current.get(k))
    if args.apply and changed:
        args.manifest.write_text(json.dumps(new,indent=2,sort_keys=True)+"\n",encoding="utf8")
    print(json.dumps({"upstream":"morluto/jacobian", "changed_fields":changed,
                      "changes_written":bool(args.apply and changed),
                      "current_runtime_pin":current["version"],
                      "latest_version":new["latest_available_version"],
                      "new_source_sha":new["upstream_main_sha"],
                      "runtime_pin_updated":False},sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
