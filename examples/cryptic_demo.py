"""Historical checkpoint replay and finite mechanism search, not new solves.

Source transcriptions and provenance are recorded beside this script.
No website, wallet, network endpoint, or downloaded code is executed.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from polya import run

DATA = Path(__file__).with_name('data') / 'cryptic-checkpoints.json'


def step(operation_id, inputs, *, input_field='text', output_field='text', rationale):
    return dict(operation_id=operation_id, inputs=inputs, input_field=input_field,
                output_field=output_field, rationale=rationale)


def main():
    fixture = json.loads(DATA.read_text(encoding='utf8'))
    grid = ''.join(fixture['gsmg_grid']['rows'])
    routes = [step('grid.traverse', dict(rows=14, columns=14, route=route, corner=corner),
                   rationale='The published clue is a square; enumerate both spiral directions from every corner.')
              for route in ['spiral_cw','spiral_ccw'] for corner in ['tl','tr','bl','br']]
    polarity = [step('encoding.symbol_map', {'mapping':m}, rationale='Test both binary color polarities.')
                for m in ({'0':'0','1':'1'},{'0':'1','1':'0'})]
    packing = [step('encoding.radix_bytes', dict(radix=2,mode='groups',group_width=8,
                    bit_order=order,tail='report'), rationale='ASCII bytes are suggested by the known challenge website.')
               for order in ['msb','lsb']]
    found = run('mechanism.scan', dict(source=grid, stages=[routes,polarity,packing],
          checkpoint=dict(kind='prefix',value='gsmg.io/',source='Public challenge hostname; not the full hidden path'),
          max_work=100000,max_trials=64))['result']
    assert found['complete'] and len(found['trials']) == 32
    assert {h['text'] for h in found['matches']} == {fixture['gsmg_grid']['expected']}
    messages = []
    for item in fixture['gsmg_decimal']:
        mapping = {chr(97+i):str(i+1) for i in range(9)} | {'o':'0'}
        digits = run('encoding.symbol_map',dict(text=item['symbols'],mapping=mapping))['result']['text']
        recovered = run('encoding.radix_bytes',dict(text=digits,radix=10))['result']['text']
        assert recovered == item['expected']
        messages.append(recovered)
    item = fixture['kryptos_k1']
    # The *whole* ciphertext is never used as plaintext evidence. Give just
    # the first ten known plaintext characters to derive the periodic key;
    # then test its consequences on the unused suffix in this replay exercise.
    reduced = run('cipher.periodic_cribs',dict(text=item['ciphertext'],alphabet=item['alphabet'],
          cribs=[dict(offset=0,text=item['plaintext'][:10],source='Retrospective K1 prefix; not a live unsolved-puzzle clue')],
          periods=list(range(1,17))))['result']
    row = next(r for r in reduced['periods'] if r['period']==10)
    assert row['key'] == 'PALIMPSEST' and row['remaining_keys'] == '1'
    plain = run('cipher.polyalphabetic',dict(text=item['ciphertext'],key=row['key'],alphabet=item['alphabet']))['result']['text']
    assert plain == item['plaintext']
    result = {'gsmg_spiral':found,'gsmg_decimal_messages':messages,
              'k1_crib_reduction':reduced,'k1_unused_suffix_matches':plain[10:]==item['plaintext'][10:],
              'scope':'Reproductions of published historical checkpoints with a caller-chosen mechanism family. '
                      'Not blinded model evaluation, not a newly solved stage, and no claimed final GSMG progress.'}
    print(json.dumps(result,indent=2))
    return result


if __name__ == '__main__':
    main()
