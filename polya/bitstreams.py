"""Bounded binary conversions with explicit conventions and source offsets.

Text offsets count Python Unicode code points. Packing offsets run from most
significant to least significant bit in each byte; slicing offsets count bytes.
No whitespace, case, Unicode, or byte-codec normalization is performed.
"""
from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_BITS = 65536
MAX_PACKED_BYTES = MAX_BITS // 8
MAX_SLICE_BYTES = 16384
SCOPE = "Exact supplied transformation; not evidence of the intended puzzle mechanism."


class Spec(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class TextSpec(Spec):
    text: str = Field(max_length=MAX_BITS)


class BitsSpec(TextSpec):
    @field_validator("text")
    @classmethod
    def binary_only(cls, value: str) -> str:
        if any(char not in "01" for char in value):
            raise ValueError("bits must contain only ASCII 0 and 1; no implicit normalization")
        return value


class InvertSpec(BitsSpec):
    invert: bool = False


class PackSpec(BitsSpec):
    bit_order: Literal["msb", "lsb"] = "msb"
    tail: Literal["reject", "drop"] = "reject"

    @model_validator(mode="after")
    def complete_groups(self) -> PackSpec:
        if self.tail == "reject" and len(self.text) % 8:
            raise ValueError("incomplete trailing byte; choose tail=drop to explicitly discard it")
        return self


class SymbolsSpec(TextSpec):
    zero: str = Field(min_length=1, max_length=1)
    one: str = Field(min_length=1, max_length=1)

    @model_validator(mode="after")
    def explicit_alphabet(self) -> SymbolsSpec:
        if self.zero == self.one:
            raise ValueError("zero and one must be distinct Unicode code points")
        if any(char not in (self.zero, self.one) for char in self.text):
            raise ValueError("text contains a symbol outside the explicit zero/one alphabet")
        return self


class SliceSpec(Spec):
    value_hex: str = Field(max_length=2 * MAX_SLICE_BYTES)
    start: int = Field(ge=0)
    stop: int = Field(ge=0)

    @field_validator("value_hex")
    @classmethod
    def strict_hex(cls, value: str) -> str:
        if re.fullmatch(r"(?:[0-9a-fA-F]{2})*", value) is None:
            raise ValueError("value_hex requires even-length hexadecimal with no whitespace or prefix")
        return value

    @model_validator(mode="after")
    def bounded_selection(self) -> SliceSpec:
        if not self.start <= self.stop <= len(self.value_hex) // 2:
            raise ValueError("slice requires 0 <= start <= stop <= source byte length")
        return self


def invert_bits(text: str, invert: bool = False) -> dict:
    p = InvertSpec(text=text, invert=invert)
    result = p.text.translate(str.maketrans("01", "10")) if p.invert else p.text
    return {"text": result, "source_offsets": list(range(len(p.text))), "scope": SCOPE}


def pack_bits(text: str, bit_order: str = "msb", tail: str = "reject") -> dict:
    p = PackSpec(text=text, bit_order=bit_order, tail=tail)
    consumed = len(p.text) - len(p.text) % 8
    packed = bytearray()
    offsets: list[list[int]] = []
    for start in range(0, consumed, 8):
        source = list(range(start, start + 8))
        if p.bit_order == "lsb":
            source.reverse()
        packed.append(int("".join(p.text[index] for index in source), 2))
        offsets.append(source)
    return {
        "hex": packed.hex(), "byte_length": len(packed), "source_offsets": offsets,
        "dropped_offsets": list(range(consumed, len(p.text))), "consumed_bits": consumed,
        "bit_order": p.bit_order, "tail": p.tail,
        "scope": SCOPE + " Exactly eight bits per byte; offsets are in most-to-least significant order.",
    }


def symbols_to_bits(text: str, zero: str, one: str) -> dict:
    p = SymbolsSpec(text=text, zero=zero, one=one)
    return {"text": "".join("0" if char == p.zero else "1" for char in p.text),
            "source_offsets": list(range(len(p.text))), "scope": SCOPE}


def slice_bytes(value_hex: str, start: int, stop: int) -> dict:
    p = SliceSpec(value_hex=value_hex, start=start, stop=stop)
    source = bytes.fromhex(p.value_hex)
    selected = source[p.start:p.stop]
    dropped = []
    if p.start:
        dropped.append([0, p.start])
    if p.stop < len(source):
        dropped.append([p.stop, len(source)])
    return {"hex": selected.hex(), "byte_length": len(selected),
            "source_offsets": list(range(p.start, p.stop)), "dropped_ranges": dropped,
            "scope": SCOPE + " Explicit half-open byte selection; dropped ranges are half-open source offsets."}


def operations(make):
    bit_offset = Annotated[int, Field(ge=0, lt=MAX_BITS)]
    bit_offsets = Annotated[list[bit_offset], Field(max_length=MAX_BITS)]
    text = Annotated[str, Field(max_length=MAX_BITS)]
    byte_offset = Annotated[int, Field(ge=0, lt=MAX_SLICE_BYTES)]
    range_endpoint = Annotated[int, Field(ge=0, le=MAX_SLICE_BYTES)]
    byte_range = Annotated[list[range_endpoint], Field(min_length=2, max_length=2)]
    return [
        make("bits.invert", "Apply an explicit binary inversion",
             "Preserve or invert every supplied binary digit while retaining code-point offsets.",
             InvertSpec, invert_bits, "bits binary invert polarity complement offsets",
             SCOPE + " invert=false preserves the input; invert=true swaps 0 and 1.",
             "0..65536 ASCII binary digits; at most 65536 output digits and source offsets; no normalization.",
             text=text, source_offsets=bit_offsets, scope=str),
        make("bits.pack", "Pack exact binary groups into bytes",
             "Pack eight-bit groups with explicit bit order and incomplete-tail handling; preserve zero bytes.",
             PackSpec, pack_bits, "bits binary pack bytes msb lsb endian tail offsets",
             SCOPE + " Source offsets list contributing bits from most to least significant; no text decoding.",
             "0..65536 ASCII binary digits; fixed 8-bit groups; at most 8192 bytes, 16384 hex digits, "
             "65536 contributing offsets and 7 explicitly dropped tail offsets.",
             hex=Annotated[str, Field(max_length=2 * MAX_PACKED_BYTES)],
             byte_length=Annotated[int, Field(ge=0, le=MAX_PACKED_BYTES)],
             source_offsets=Annotated[list[Annotated[list[bit_offset], Field(min_length=8, max_length=8)]],
                                      Field(max_length=MAX_PACKED_BYTES)],
             dropped_offsets=Annotated[list[bit_offset], Field(max_length=7)],
             consumed_bits=Annotated[int, Field(ge=0, le=MAX_BITS)],
             bit_order=Literal["msb", "lsb"], tail=Literal["reject", "drop"], scope=str),
        make("symbols.to_bits", "Map an explicit two-symbol alphabet to bits",
             "Map distinct single-code-point zero and one symbols without changing or dropping input.",
             SymbolsSpec, symbols_to_bits, "symbols binary alphabet mapping bits unicode offsets",
             SCOPE + " Every source code point must be one of the two explicitly declared symbols.",
             "0..65536 Unicode code points; two distinct single-code-point symbols; "
             "at most 65536 output bits and source offsets; no normalization.",
             text=text, source_offsets=bit_offsets, scope=str),
        make("bytes.slice", "Select an explicit half-open byte range",
             "Select bytes by start/stop offsets and report every discarded prefix and suffix range.",
             SliceSpec, slice_bytes, "bytes slice select range prefix suffix offsets binary",
             SCOPE + " Requires 0 <= start <= stop <= source byte length; no implicit truncation.",
             "0..32768 even hexadecimal digits (0..16384 source bytes); at most 16384 selected bytes "
             "and source offsets; at most 2 nonempty half-open dropped ranges; no whitespace or prefix.",
             hex=Annotated[str, Field(max_length=2 * MAX_SLICE_BYTES)],
             byte_length=Annotated[int, Field(ge=0, le=MAX_SLICE_BYTES)],
             source_offsets=Annotated[list[byte_offset], Field(max_length=MAX_SLICE_BYTES)],
             dropped_ranges=Annotated[list[byte_range], Field(max_length=2)], scope=str),
    ]
