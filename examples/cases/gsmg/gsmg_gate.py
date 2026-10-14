"""Offline hypothesis profile for the published SalPhaseIon lock, not a solution.

The SHA256 EVP digest here is a declared hypothesis for the unknown lock.
Passing the public phase-2 control does NOT prove it is the final lock's digest.
No passwords are guessed here. Supply outputs of your own source-linked recipes.
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from polya import run
from polya.jsonio import loads


def make_plan(candidates: list[dict]) -> dict:
    control = loads(Path(__file__).with_name('gsmg-phase2-control.json').read_text())
    blob = base64.b64decode(
        'U2FsdGVkX186tYU0hVJBXXUnBUO7C0+X4KUWnWkCvoZSxbRD3wNsGWVHefvdrd9z'
        'QvX0t8v3jPB4okpspxebRi6sE1BMl5HI8Rku+KejUqTvdWOX6nQjSpepXwGuN/jJ').hex()
    return {'candidates': candidates, 'max_trials': 512, 'locks': [
        {'id': 'salphaseion-' + reading, 'blob_hex': blob,
         'digest': 'sha256', 'password_mode': 'sha256_hex', 'calibration': control,
         'target': {'kind': 'p2pkh', 'value': '1GSMG1JC9wtdSwfwApgj2xcmJPAwx7prBe',
            'source': 'Published GSMG target; plaintext reading is a hypothesis',
            'reading': reading, 'compressed': False}}
        for reading in ('sha256', 'first32', 'last32', 'ascii_hex')]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates', required=True, help='JSON list of id/value_hex/source objects')
    args = parser.parse_args()
    with open(args.candidates, encoding='utf8') as stream:
        raw = stream.read(1000001)
    if len(raw) > 1000000:
        parser.error('candidate file exceeds 1 MB')
    report = run('crypto.openssl_scan', make_plan(loads(raw)))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
