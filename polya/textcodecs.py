"""Strict text/byte boundaries. No replacement, normalization, or codec guessing."""
from __future__ import annotations

from typing import Literal
from pydantic import Field
from .cryptic import Spec
from .crypto_targets import raw_hex

LIMIT = 16384
Codec = Literal['ascii', 'utf-8', 'latin-1']
SCOPE = 'Exact encoding under the specified codec; no normalization or error repair.'


class EncodeInput(Spec):
    text: str = Field(max_length=LIMIT)
    codec: Codec


class DecodeInput(Spec):
    value_hex: str = Field(max_length=LIMIT * 2)
    codec: Codec


def _spans(text: str, codec: str) -> list[list[int]]:
    cursor, spans = 0, []
    for char in text:
        end = cursor + len(char.encode(codec, errors='strict'))
        spans.append([cursor, end])
        cursor = end
    return spans


def encode_text(text: str, codec: str) -> dict:
    p = EncodeInput(text=text, codec=codec)
    raw = p.text.encode(p.codec, errors='strict')
    if len(raw) > LIMIT:
        raise ValueError('encoded output exceeds 16384 bytes; select a smaller explicit source')
    return {'hex': raw.hex(), 'byte_length': len(raw), 'codepoint_length': len(text),
            'codepoint_byte_spans': _spans(text, codec), 'codec': codec, 'scope': SCOPE}


def decode_text(value_hex: str, codec: str) -> dict:
    p = DecodeInput(value_hex=value_hex, codec=codec)
    raw = raw_hex(p.value_hex, LIMIT)
    text = raw.decode(p.codec, errors='strict')
    return {'text': text, 'byte_length': len(raw), 'codepoint_length': len(text),
            'codepoint_byte_spans': _spans(text, codec), 'codec': codec, 'scope': SCOPE}


def operations(make):
    common = dict(byte_length=int, codepoint_length=int,
                  codepoint_byte_spans=list[list[int]], codec=str, scope=str)
    return [
        make('text.encode', 'Encode text as exact bytes',
             'Choose ascii, utf-8, or latin-1 explicitly; keep the byte span of each code point.',
             EncodeInput, encode_text, 'text encode utf8 ascii latin1 bytes conversion plan', SCOPE,
             '16384 source code points and encoded bytes; errors are rejected, never replaced.',
             example={'text': 'A雪', 'codec': 'utf-8'}, hex=str, **common),
        make('bytes.decode_text', 'Decode exact bytes as text',
             'Decode strict hexadecimal bytes under an explicit codec, retaining source byte spans.',
             DecodeInput, decode_text, 'bytes decode text utf8 ascii latin1 conversion plan', SCOPE,
             '16384 source bytes; only ascii, utf-8 and latin-1. Invalid byte sequences are errors.',
             example={'value_hex': '41e99baa', 'codec': 'utf-8'}, text=str, **common),
    ]
