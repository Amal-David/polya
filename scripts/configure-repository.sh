#!/usr/bin/env bash
# Apply the checked-in About description and add its topics using an authenticated gh CLI.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v gh >/dev/null || { echo 'GitHub CLI (gh) is required.' >&2; exit 1; }
python - <<'PYCODE'
import json, subprocess
from pathlib import Path
meta = json.loads(Path('.github/repository.json').read_text())
cmd = ['gh', 'repo', 'edit', meta['repository'], '--description', meta['description']]
for topic in meta['topics']:
    cmd.extend(['--add-topic', topic])
subprocess.run(cmd, check=True)
subprocess.run(['gh', 'repo', 'view', meta['repository'], '--json', 'description,repositoryTopics'], check=True)
PYCODE
