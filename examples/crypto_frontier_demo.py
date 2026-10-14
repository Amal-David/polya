"""Exercise a missing bridge: raw PNG -> explicit candidate programs -> calibrated lock.

Fresh synthetic instances with withheld channel/bit/route parameters. The search
receives no plaintext, password, or hidden parameters. The grammar is supplied;
this is not learned mechanism discovery or evidence of improved LLM reasoning.
"""
from __future__ import annotations

import json
from pathlib import Path
from polya import run

DATA = Path(__file__).with_name('data')


def extract_candidates(png_base64: str) -> list[dict]:
    candidates = []
    for channel in ('R', 'G', 'B'):
        for bit in (0, 1):
            plane = run('artifact.png_bitplane', {'png_base64': png_base64,
                'channel': channel, 'bit': bit})['result']
            for order in ('row', 'column', 'row_snake', 'column_snake'):
                for reverse in (False, True):
                    bits = run('grid.read', {'text': plane['text'], 'rows': plane['height'],
                        'columns': plane['width'], 'order': order, 'reverse': reverse})['result']['text']
                    if len(bits) % 8:
                        raise ValueError('this demonstration requires whole bytes; no tail is discarded')
                    for invert in (False, True):
                        transformed = bits.translate(str.maketrans('01', '10')) if invert else bits
                        for lsb in (False, True):
                            groups = [transformed[i:i+8] for i in range(0,len(transformed),8)]
                            raw = bytes(int(group[::-1] if lsb else group, 2) for group in groups)
                            name = f'{channel}.b{bit}.{order}.rev{int(reverse)}.inv{int(invert)}.lsb{int(lsb)}'
                            candidates.append({'id': name, 'value_hex': raw.hex(),
                                'source': 'PNG SHA256 '+plane['source_sha256']+'; explicit recipe '+name})
    return candidates


def main() -> dict:
    cases = json.loads((DATA/'crypto-hidden-parameters.json').read_text())
    outputs = []
    for case in cases:
        candidates = extract_candidates(case['png_base64'])
        result = run('crypto.openssl_scan', {'candidates': candidates, 'locks': [case['lock']]})['result']
        assert result['complete'] and result['matches']
        distinct_matches = {c['value_hex'] for c in candidates
                            if c['id'] in {r['candidate_id'] for r in result['matches']}}
        assert len(distinct_matches) == 1
        outputs.append({'case': case['id'], 'candidate_programs': len(candidates),
            'unique_candidate_bytes': len({c['value_hex'] for c in candidates}),
            'matching_programs': [r['candidate_id'] for r in result['matches']],
            'crypto_calls': result['crypto_calls'], 'complete': result['complete']})
    control = json.loads((DATA/'gsmg-phase2-control.json').read_text())
    result = run('crypto.openssl_scan', {'candidates': [
        {'id': 'published-phase2-answer', 'value_hex': control['candidate_hex'], 'source': control['source']}],
        'locks': [{'id': 'historical-phase2', 'blob_hex': control['blob_hex'], 'digest': 'sha256',
            'password_mode': 'sha256_hex', 'calibration': control,
            'target': {'kind': 'sha256', 'value': control['plaintext_sha256'],
                       'source': 'OpenSSL-reproduced historical plaintext hash'}}]})['result']
    assert result['complete'] and len(result['matches']) == 1
    return {'synthetic_cases': outputs, 'historical_phase2_reproduced': True,
        'scope': 'Three synthetic supplied-grammar parameter recoveries and one public decryption calibration. '
        'No LLM was evaluated. No new GSMG stage or final password was recovered. '
        'The historical scan reuses its calibration computation, not independent evidence.'}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
