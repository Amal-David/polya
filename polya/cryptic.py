"""Exact, bounded classical-cipher and extraction operations for public puzzles.

No implicit case folding, alphabet repair, whitespace deletion, or live queries.
Offsets always count Python Unicode code points, not UTF-8 bytes or glyphs.
"""
from __future__ import annotations

from math import isqrt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_TEXT = 16384
SCOPE = "Exact supplied transformation; not evidence of the intended puzzle mechanism."


class Spec(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class TextSpec(Spec):
    text: str = Field(max_length=MAX_TEXT)


class RouteSpec(TextSpec):
    rows: int = Field(ge=1, le=MAX_TEXT)
    columns: int = Field(ge=1, le=MAX_TEXT)
    route: Literal["row", "column", "row_snake", "column_snake", "spiral_cw", "spiral_ccw"]
    corner: Literal["tl", "tr", "bl", "br"] = "tl"
    reverse: bool = False


def route_text(text: str, rows: int, columns: int, route: str,
               corner: str = "tl", reverse: bool = False) -> dict:
    p = RouteSpec(text=text, rows=rows, columns=columns, route=route,
                  corner=corner, reverse=reverse)
    if p.rows * p.columns != len(p.text):
        raise ValueError("grid shape must account for every source character")
    if route == "row":
        coords = [(r, c) for r in range(rows) for c in range(columns)]
    elif route == "column":
        coords = [(r, c) for c in range(columns) for r in range(rows)]
    elif route == "row_snake":
        coords = [(r, c) for r in range(rows)
                  for c in (range(columns) if r % 2 == 0 else range(columns-1, -1, -1))]
    elif route == "column_snake":
        coords = [(r, c) for c in range(columns)
                  for r in (range(rows) if c % 2 == 0 else range(rows-1, -1, -1))]
    else:
        # Reflecting just one axis changes handedness; compensate so cw/ccw
        # retains its geometric meaning at all four starting corners.
        clockwise = route == "spiral_cw"
        if corner in ("tr", "bl"):
            clockwise = not clockwise
        directions = [(0,1),(1,0),(0,-1),(-1,0)] if clockwise else [(1,0),(0,1),(-1,0),(0,-1)]
        r = c = d = 0
        coords, seen = [], set()
        for _ in range(rows * columns):
            coords.append((r,c)); seen.add((r,c))
            for _ in range(4):
                dr, dc = directions[d]
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < columns and (nr,nc) not in seen:
                    r,c = nr,nc
                    break
                d = (d+1) % 4
    offsets = [((rows-1-r if corner[0] == "b" else r) * columns
                + (columns-1-c if corner[1] == "r" else c)) for r,c in coords]
    if reverse:
        offsets.reverse()
    return {"text": "".join(text[i] for i in offsets), "source_offsets": offsets,
            "source_length": len(text), "scope": SCOPE}


class MapSpec(TextSpec):
    mapping: dict[str, str]


def symbol_map(text: str, mapping: dict[str, str]) -> dict:
    MapSpec(text=text, mapping=mapping)
    if not 1 <= len(mapping) <= 256 or any(len(k) != 1 or len(v) > 32 for k,v in mapping.items()):
        raise ValueError("mapping needs 1..256 single-character keys and outputs of at most 32 characters")
    if set(text) - mapping.keys():
        raise ValueError("unmapped characters: provide an explicit mapping (including whitespace)")
    out, offsets, dropped = [], [], []
    for i, char in enumerate(text):
        token = mapping[char]
        out.append(token); offsets.extend([i] * len(token))
        if not token:
            dropped.append(i)
    result = "".join(out)
    if len(result) > MAX_TEXT:
        raise ValueError("mapped output exceeds text limit")
    return {"text": result, "source_offsets": offsets, "dropped_offsets": dropped,
            "source_length": len(text), "scope": SCOPE}


class RadixSpec(TextSpec):
    radix: Literal[2, 8, 10, 16]
    mode: Literal["integer", "groups"] = "integer"
    group_width: int = Field(default=8, ge=1, le=8)
    bit_order: Literal["msb", "lsb"] = "msb"
    tail: Literal["reject", "report"] = "reject"
    codec: Literal["ascii", "utf-8", "latin-1"] = "ascii"
    min_bytes: int = Field(default=1, ge=1, le=2048)


def radix_bytes(text: str, radix: int, mode: str = "integer", group_width: int = 8,
                bit_order: str = "msb", tail: str = "reject", codec: str = "ascii",
                min_bytes: int = 1) -> dict:
    RadixSpec(text=text, radix=radix, mode=mode, group_width=group_width,
              bit_order=bit_order, tail=tail, codec=codec, min_bytes=min_bytes)
    alphabet = "0123456789abcdef"[:radix]
    # Deliberately accept either hex case, but no signs, prefixes or whitespace.
    if not text or any(c.lower() not in alphabet for c in text):
        raise ValueError("nonempty unsigned digits of the explicit radix are required")
    if len(text) > 2048:
        raise ValueError("radix input is limited to 2048 digits")
    remainder = ""
    if mode == "integer":
        if bit_order != "msb":
            raise ValueError("lsb ordering is defined only for fixed-width binary groups")
        value = int(text, radix)
        raw = value.to_bytes(max(min_bytes, (value.bit_length()+7)//8), "big")
        consumed = len(text)
    else:
        if bit_order == "lsb" and radix != 2:
            raise ValueError("lsb ordering is defined only for binary groups")
        consumed = len(text) - len(text) % group_width
        remainder = text[consumed:]
        if remainder and tail == "reject":
            raise ValueError("incomplete trailing group; choose tail=report to preserve it explicitly")
        numbers = [int(text[i:i+group_width][::-1] if bit_order == "lsb" else text[i:i+group_width], radix)
                   for i in range(0, consumed, group_width)]
        if any(n > 255 for n in numbers):
            raise ValueError("group value is outside one byte")
        raw = bytes(numbers)
    decoded = None
    try:
        decoded = raw.decode(codec, errors="strict")
    except UnicodeDecodeError:
        pass
    return {"hex": raw.hex(), "text": decoded, "byte_count": len(raw),
            "consumed_digits": consumed, "trailing_digits": remainder,
            "leading_zero_digits": len(text) - len(text.lstrip("0")),
            "scope": SCOPE + " Integer mode uses minimal big-endian bytes with explicit min_bytes."}


class AlphabetSpec(TextSpec):
    alphabet: str = Field(default="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_length=2, max_length=256)
    key: str = Field(min_length=1, max_length=MAX_TEXT)
    variant: Literal["vigenere", "beaufort", "variant_beaufort"] = "vigenere"
    action: Literal["encrypt", "decrypt"] = "decrypt"


def alphabet_ids(alphabet: str) -> dict[str, int]:
    if not 2 <= len(alphabet) <= 256 or len(set(alphabet)) != len(alphabet):
        raise ValueError("alphabet must have 2..256 distinct code points")
    return {c:i for i,c in enumerate(alphabet)}


def polyalphabetic(text: str, key: str, alphabet: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                  variant: str = "vigenere", action: str = "decrypt") -> dict:
    AlphabetSpec(text=text, key=key, alphabet=alphabet, variant=variant, action=action)
    ids = alphabet_ids(alphabet)
    if (set(text) | set(key)) - ids.keys():
        raise ValueError("text/key contain characters outside the explicit alphabet")
    n = len(alphabet)
    out = []
    for i,c in enumerate(text):
        x,k = ids[c], ids[key[i % len(key)]]
        if variant == "beaufort":
            y = k-x
        elif (variant == "vigenere") == (action == "encrypt"):
            y = x+k
        else:
            y = x-k
        out.append(alphabet[y % n])
    return {"text": "".join(out), "source_offsets": list(range(len(text))),
            "scope": SCOPE + " No alphabet normalization; key advances on every supplied character."}


class BifidSpec(TextSpec):
    square: str = Field(min_length=4, max_length=256)
    period: int = Field(ge=1, le=MAX_TEXT)
    action: Literal["encrypt", "decrypt"] = "decrypt"


def bifid(text: str, square: str, period: int, action: str = "decrypt") -> dict:
    BifidSpec(text=text, square=square, period=period, action=action)
    width = isqrt(len(square))
    if width * width != len(square) or len(set(square)) != len(square):
        raise ValueError("square must contain n*n distinct characters")
    ids = {c:divmod(i,width) for i,c in enumerate(square)}
    if set(text) - ids.keys():
        raise ValueError("text contains characters outside square; no implicit I/J merging")
    output = []
    for start in range(0, len(text), period):
        block = text[start:start+period]
        pairs = [ids[c] for c in block]
        if action == "encrypt":
            flat = [r for r,c in pairs] + [c for r,c in pairs]
            output.extend(square[flat[i]*width+flat[i+1]] for i in range(0,len(flat),2))
        else:
            flat = [v for pair in pairs for v in pair]
            output.extend(square[flat[i]*width+flat[len(block)+i]] for i in range(len(block)))
    return {"text": "".join(output), "block_lengths": [min(period,len(text)-i) for i in range(0,len(text),period)],
            "scope": SCOPE + " The final short block uses its actual length."}


class CheckerSpec(TextSpec):
    codes: dict[str, str]


def checkerboard(text: str, codes: dict[str, str]) -> dict:
    CheckerSpec(text=text, codes=codes)
    if not 1 <= len(codes) <= 100 or any(not c or len(c)>2 or not c.isascii() or not c.isdigit()
                                        or len(v)!=1 for c,v in codes.items()):
        raise ValueError("provide 1..100 one/two-digit codes mapped to single characters")
    ordered = sorted(codes)
    if any(b.startswith(a) for i,a in enumerate(ordered) for b in ordered[i+1:]):
        raise ValueError("codebook must be prefix-free")
    if not text.isascii() or (text and not text.isdigit()):
        raise ValueError("checkerboard input must contain only ASCII digits")
    out, spans, i = [], [], 0
    while i < len(text):
        found = next((text[i:i+n] for n in (1,2) if text[i:i+n] in codes), None)
        if found is None:
            raise ValueError(f"no complete code at source offset {i}")
        out.append(codes[found]); spans.append([i,i+len(found)]); i += len(found)
    return {"text": "".join(out), "source_spans": spans, "consumed_digits": i, "scope": SCOPE}


class Crib(Spec):
    offset: int = Field(ge=0, le=MAX_TEXT)
    text: str = Field(min_length=1, max_length=MAX_TEXT)
    source: str = Field(min_length=1, max_length=256)


class CribsSpec(TextSpec):
    cribs: list[Crib] = Field(min_length=1, max_length=64)
    periods: list[int] = Field(min_length=1, max_length=256)
    alphabet: str = Field(default="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_length=2, max_length=256)
    variant: Literal["vigenere", "beaufort", "variant_beaufort"] = "vigenere"


def periodic_cribs(text: str, cribs: list[dict], periods: list[int],
                   alphabet: str = "ABCDEFGHIJKLMNOPQRSTUVWXYZ", variant: str = "vigenere") -> dict:
    p = CribsSpec(text=text, cribs=cribs, periods=periods, alphabet=alphabet, variant=variant)
    if len(set(periods)) != len(periods) or any(type(n) is not int or not 1 <= n <= 1024 for n in periods):
        raise ValueError("periods must be distinct integers in 1..1024")
    if sum(len(c.text) for c in p.cribs) > MAX_TEXT:
        raise ValueError("total crib length exceeds work limit")
    ids = alphabet_ids(alphabet); n = len(alphabet)
    if set(text) - ids.keys():
        raise ValueError("ciphertext outside alphabet")
    equations = []
    for c in p.cribs:
        if c.offset+len(c.text)>len(text) or set(c.text)-ids.keys():
            raise ValueError("crib extends outside ciphertext or alphabet")
        for j,char in enumerate(c.text):
            pos = c.offset+j; cv,pv = ids[text[pos]],ids[char]
            value = (cv-pv if variant=="vigenere" else pv-cv if variant=="variant_beaufort" else pv+cv) % n
            equations.append({"position":pos,"key_value":value,"source":c.source,
                              "plaintext":char,"ciphertext":text[pos]})
    candidates = []
    for period in periods:
        slots, conflict = {}, None
        for e in equations:
            slot = e["position"] % period
            if slot in slots and slots[slot]["key_value"] != e["key_value"]:
                conflict = {"key_slot":slot,"first":slots[slot],"second":e}
                break
            slots[slot] = e
        chars = [alphabet[slots[i]["key_value"]] if i in slots else None for i in range(period)]
        free = sum(c is None for c in chars)
        remaining = 0 if conflict else n**free
        candidates.append({"period":period,"consistent":conflict is None,
                           "key_slots":chars if conflict is None else None,"conflict":conflict,
                           "remaining_keys":str(remaining),
                           "key": "".join(chars) if conflict is None and free == 0 else None})
    return {"periods":candidates,"crib_equations":len(equations),
            "scope":"Exact elimination inside the supplied alphabet/variant/periodic-key model and caller cribs only. "
                    "A surviving period is not evidence for the model; a conflict does not refute other mechanisms."}


def operations(make):
    def op(oid,title,request,kernel,terms,post,**fields):
        return make(oid,title,title,request,kernel,terms,post,
                    "Bounded text, explicit alphabets and normalization; inspect input schema.",**fields)
    return [
        op("grid.traverse","Traverse a grid including corner-aware spirals",RouteSpec,route_text,
           "spiral grid route geometry transposition extraction gsmg",SCOPE,text=str,source_offsets=list[int],source_length=int,scope=str),
        op("text.symbol_map","Map symbols without silent deletion",MapSpec,symbol_map,
           "binary mapping substitute symbols digits a1z26 salphaseion",SCOPE,text=str,source_offsets=list[int],dropped_offsets=list[int],source_length=int,scope=str),
        op("bytes.from_radix","Decode radix groups or a whole integer",RadixSpec,radix_bytes,
           "binary decimal hex ascii bytes integer radix endian packing",SCOPE,hex=str,text=str|None,byte_count=int,
           consumed_digits=int,trailing_digits=str,leading_zero_digits=int,scope=str),
        op("cipher.polyalphabetic","Transform Vigenere or Beaufort with an explicit alphabet",AlphabetSpec,polyalphabetic,
           "vigenere beaufort variant keyed alphabet polyalphabetic decrypt encrypt",SCOPE,text=str,source_offsets=list[int],scope=str),
        op("cipher.bifid","Transform Bifid with an explicit square and period",BifidSpec,bifid,
           "bifid polybius fractionation period classical cipher gsmg",SCOPE,text=str,block_lengths=list[int],scope=str),
        op("cipher.checkerboard","Decode an explicit prefix-free checkerboard",CheckerSpec,checkerboard,
           "straddling checkerboard digits escape prefix cipher gsmg",SCOPE,text=str,source_spans=list[list[int]],consumed_digits=int,scope=str),
        op("cipher.periodic_cribs","Eliminate periodic keys using source-labelled cribs",CribsSpec,periodic_cribs,
           "crib known plaintext periodic key eliminate recover contradiction cryptanalysis kryptos",
           "Exact necessary key constraints and local contradictions for the declared cipher family; no language-model score.",
           periods=list[dict],crib_equations=int,scope=str),
    ]
