"""Render a hash-locked requirement for the reviewed *runtime* wheel, offline.

Observed upstream/latest fields never select installed code. This pins Jacobian's
wheel only; its transitive dependencies are resolved separately, not hash locked.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

PIN = Path(__file__).resolve().parents[1] / 'polya' / 'jacobian_pin.json'


def requirement(pin: dict) -> str:
    if pin.get('upstream') != 'morluto/jacobian':
        raise ValueError('unexpected Jacobian upstream')
    version, digest = pin.get('version'), pin.get('wheel_sha256')
    if not isinstance(version, str) or re.fullmatch(r'\d+\.\d+\.\d+', version) is None:
        raise ValueError('runtime version must be an exact stable version')
    if not isinstance(digest, str) or re.fullmatch(r'[0-9a-f]{64}', digest) is None:
        raise ValueError('reviewed runtime wheel needs a lowercase SHA256 digest')
    return f'jacobian=={version} --hash=sha256:{digest}\n'


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pin', type=Path, default=PIN)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    value = requirement(json.loads(args.pin.read_text(encoding='utf-8')))
    if args.output:
        args.output.write_text(value, encoding='utf-8')
    else:
        print(value, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
