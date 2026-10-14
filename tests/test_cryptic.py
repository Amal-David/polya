"""Independent arithmetic/coordinate checks, not just encrypt/decrypt round trips."""
from itertools import product
import random
import pytest
from polya import run, find
from polya.cryptic import (bifid, checkerboard, periodic_cribs, polyalphabetic,
                           radix_bytes, route_text, symbol_map)


def peel(height, width):
    grid = [[r*width+c for c in range(width)] for r in range(height)]
    out = []
    while grid:
        out.extend(grid.pop(0))
        if not grid:
            break
        # Counter-clockwise rotation makes the next perimeter edge the top row.
        grid = [list(row) for row in zip(*grid)][::-1]
    return out


@pytest.mark.parametrize('height,width', product(range(1,8), repeat=2))
def test_spiral_independent_peeling_and_inverse(height,width):
    text=''.join(chr(0x100+i) for i in range(height*width))
    for corner in ['tl','tr','bl','br']:
        for route in ['row','column','row_snake','column_snake','spiral_cw','spiral_ccw']:
            r=route_text(text,height,width,route,corner)
            assert sorted(r['source_offsets']) == list(range(len(text)))
            reconstructed=['']*len(text)
            for c,i in zip(r['text'],r['source_offsets']): reconstructed[i]=c
            assert ''.join(reconstructed)==text
    assert route_text(text,height,width,'spiral_cw')['source_offsets']==peel(height,width)


def test_geometric_handedness_corner_and_reverse():
    expected={('tl','spiral_cw'):'123698745',('tl','spiral_ccw'):'147896325',
              ('tr','spiral_cw'):'369874125',('tr','spiral_ccw'):'321478965',
              ('br','spiral_cw'):'987412365',('br','spiral_ccw'):'963214785',
              ('bl','spiral_cw'):'741236985',('bl','spiral_ccw'):'789632145'}
    for (corner,route),out in expected.items():
        assert route_text('123456789',3,3,route,corner)['text']==out
        assert route_text('123456789',3,3,route,corner,True)['text']==out[::-1]


def test_map_coverage_and_radix_information_loss():
    mapped=symbol_map('a b',{'a':'00',' ':'','b':'1'})
    assert mapped['text']=='001' and mapped['source_offsets']==[0,0,2]
    assert mapped['dropped_offsets']==[1]
    assert radix_bytes('0065',10)['hex']=='41'
    assert radix_bytes('0065',10,min_bytes=2)['hex']=='0041'
    assert radix_bytes('1000001',2,mode='groups',group_width=7)['text']=='A'
    assert radix_bytes('1000001011',2,mode='groups',group_width=8,bit_order='lsb',tail='report')['text']=='A'
    assert radix_bytes('1000001011',2,mode='groups',group_width=8,bit_order='lsb',tail='report')['trailing_digits']=='11'
    assert radix_bytes('ff',16,codec='ascii')['text'] is None
    assert radix_bytes('ff',16,codec='latin-1')['text']=='\xff'


@pytest.mark.parametrize('call',[
    lambda:route_text('abc',2,2,'row'),
    lambda:symbol_map('a ',{'a':'1'}),
    lambda:symbol_map('a',{'aa':'1'}),
    lambda:radix_bytes('0b11',2),lambda:radix_bytes('-3',10),lambda:radix_bytes('１２',10),
    lambda:radix_bytes('101',2,mode='groups'),
    lambda:radix_bytes('999',10,mode='groups',group_width=3),
    lambda:radix_bytes('12',10,bit_order='lsb'),
    lambda:polyalphabetic('a','A'),lambda:polyalphabetic('A','A',alphabet='AA'),
    lambda:bifid('A','ABCDE',1),lambda:bifid('J','ABCDEFGHIKLMNOPQRSTUVWXYZ',3),
    lambda:checkerboard('11',{'1':'A','11':'B'}),lambda:checkerboard('1',{'11':'A'}),
    lambda:periodic_cribs('ABC',[{'offset':0,'text':'A','source':'clue'}],[True]),
    lambda:periodic_cribs('ABC',[{'offset':2,'text':'AA','source':'clue'}],[1]),
])
def test_reject_invalid_and_never_silently_normalize(call):
    with pytest.raises(ValueError): call()


def reference_encrypt(text,square,period):
    side=int(len(square)**0.5)
    locations={c:(str(i//side),str(i%side)) for i,c in enumerate(square)}
    result=''
    for start in range(0,len(text),period):
        points=[locations[c] for c in text[start:start+period]]
        digits=''.join(r for r,c in points)+''.join(c for r,c in points)
        result+=''.join(square[int(digits[i])*side+int(digits[i+1])] for i in range(0,len(digits),2))
    return result


@pytest.mark.parametrize('seed',range(20))
def test_bifid_against_independent_coordinate_strings(seed):
    rng=random.Random(seed)
    for side in (2,3,5):
        square=''.join(rng.sample('ABCDEFGHIJKLMNOPQRSTUVWXYZ'[:side*side],side*side))
        text=''.join(rng.choices(square,k=rng.randrange(1,100)))
        for period in (1,2,7,len(text),len(text)+1):
            expected=reference_encrypt(text,square,period)
            assert bifid(text,square,period,'encrypt')['text']==expected
            assert bifid(expected,square,period)['text']==text


def encrypt(plain,key,alphabet,variant):
    p=[alphabet.index(c) for c in plain]; k=[alphabet.index(c) for c in key]
    def f(x,y):
        return x+y if variant=='vigenere' else x-y if variant=='variant_beaufort' else y-x
    return ''.join(alphabet[f(x,k[i%len(k)])%len(alphabet)] for i,x in enumerate(p))


@pytest.mark.parametrize('seed',range(12))
@pytest.mark.parametrize('variant',['vigenere','beaufort','variant_beaufort'])
def test_crib_counts_against_exhaustive_keys(seed,variant):
    rng=random.Random(seed); alphabet='ABC'
    plain=''.join(rng.choices(alphabet,k=12)); key=''.join(rng.choices(alphabet,k=3))
    cipher=encrypt(plain,key,alphabet,variant)
    assert polyalphabetic(cipher,key,alphabet,variant)['text']==plain
    cribs=[{'offset':0,'text':plain[:3],'source':'clue-1'},
           {'offset':6,'text':plain[6:8],'source':'clue-2'}]
    if seed%2:
        cribs[1]['text']=rng.choice(alphabet)+cribs[1]['text'][1:]
    got=periodic_cribs(cipher,cribs,[1,2,3,4],alphabet,variant)
    for row in got['periods']:
        valid=[]
        for k in product(alphabet,repeat=row['period']):
            word=''.join(k)
            # Compare crib encryption directly with ciphertext, including key phase.
            ok=all(encrypt(c['text'],word[c['offset']%len(word):]+word[:c['offset']%len(word)],alphabet,variant)
                   == cipher[c['offset']:c['offset']+len(c['text'])] for c in cribs)
            if ok: valid.append(word)
        assert int(row['remaining_keys']) == len(valid)
        assert row['consistent'] == bool(valid)
        if row['key'] is not None: assert valid==[row['key']]
        if row['conflict']:
            c=row['conflict']; assert c['first']['position']%row['period']==c['second']['position']%row['period']
            assert c['first']['key_value']!=c['second']['key_value']


def test_checkerboard_roundtrip_independent_code_concatenation():
    codes={'0':'A','2':'B','10':'C','11':'D','40':'E','41':'F'}
    digits='011210404111'  # 0 | 11 | 2 | 10 | 40 | 41 | 11 = A D B C E F D
    r=checkerboard(digits,codes)
    assert r['text']=='ADBCEFD'
    assert ''.join({v:k for k,v in codes.items()}[c] for c in r['text'])==digits
    assert r['source_spans'][0]==[0,1] and r['source_spans'][-1][1]==len(digits)


def test_public_schemas_discovery_and_no_boolean_numeric_inputs():
    for oid in ['cipher.bifid','cipher.polyalphabetic','cipher.checkerboard','cipher.periodic_cribs',
                'grid.traverse','encoding.symbol_map','encoding.radix_bytes']:
        c=find(operation_id=oid)
        assert c['input_schema']['additionalProperties'] is False
        assert c['output_schema']['additionalProperties'] is False
    assert find('bifid')[0]['operation_id']=='cipher.bifid'
    with pytest.raises(ValueError):run('encoding.radix_bytes',{'text':'10','radix':True})
