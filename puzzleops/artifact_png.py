"""Lossless, explicitly selected 8-bit PNG sample-plane extraction.

The image is data, never instructions. No resizing, EXIF orientation, palette
expansion, thresholding, OCR or image generation is performed.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import struct
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PngInput(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid')
    png_base64: str = Field(min_length=1, max_length=524288)
    channel: Literal['L', 'R', 'G', 'B', 'A', 'index']
    bit: int = Field(ge=0, le=7)
    max_pixels: int = Field(default=16384, ge=1, le=65536)


def png_bitplane(png_base64: str, channel: str, bit: int, max_pixels: int = 16384) -> dict:
    p = PngInput(png_base64=png_base64, channel=channel, bit=bit, max_pixels=max_pixels)
    try:
        raw = base64.b64decode(p.png_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError('expected canonical base64 PNG bytes') from exc
    if base64.b64encode(raw).decode('ascii') != p.png_base64:
        raise ValueError('noncanonical base64 encoding')
    if len(raw) < 33 or raw[:16] != b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR':
        raise ValueError('expected a PNG with a standard IHDR')
    width, height, depth, color = struct.unpack('>IIBB', raw[16:26])
    if not width or not height or width * height > p.max_pixels:
        raise ValueError('PNG dimensions exceed the requested pixel budget')
    if depth != 8 or color not in (0, 2, 3, 6):
        raise ValueError('only 8-bit L, RGB, palette-index or RGBA PNGs are supported')
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError('PNG extraction requires the optional imaging extra; no extraction occurred') from exc
    try:
        with Image.open(io.BytesIO(raw)) as img:
            if img.format != 'PNG' or img.size != (width, height) or getattr(img, 'n_frames', 1) != 1:
                raise ValueError('expected a single-frame PNG with unchanged dimensions')
            mode = img.mode
            allowed = {'L': ('L',), 'RGB': ('R', 'G', 'B'),
                       'RGBA': ('R', 'G', 'B', 'A'), 'P': ('index',)}
            if p.channel not in allowed.get(mode, ()):
                raise ValueError('channel is not a native sample channel; no implicit conversion is allowed')
            img.verify()
        with Image.open(io.BytesIO(raw)) as img:
            img.load()
            samples = img.tobytes() if mode in ('L', 'P') else img.getchannel(p.channel).tobytes()
    except (OSError, SyntaxError) as exc:
        raise ValueError('invalid or damaged PNG') from exc
    if len(samples) != width * height:
        raise RuntimeError('decoder sample count does not match the admitted dimensions')
    bits = ''.join('1' if value & (1 << p.bit) else '0' for value in samples)
    return {'text': bits, 'width': width, 'height': height, 'mode': mode,
            'channel': p.channel, 'bit': p.bit, 'source_sha256': hashlib.sha256(raw).hexdigest(),
            'samples_sha256': hashlib.sha256(samples).hexdigest(),
            'coordinates': 'row-major: text[y * width + x] comes from PNG sample (x,y); origin top-left',
            'scope': 'Exact selected sample bit plane of the supplied PNG. No resizing or normalization. '
                     'A palette index is not a color channel. No hidden-message interpretation is established.'}


def operations(make):
    return [make('artifact.png_bitplane', 'Extract a lossless PNG sample bit plane',
        'Preserve original image hash and pixel coordinates while extracting a selected native channel/bit.',
        PngInput, png_bitplane, 'png image pixel bits steganography bitplane extraction channel gsmg',
        'Exact supplied PNG sample plane, not automatic steganography detection or a solution.',
        '393216 encoded-source bytes, at most65536 decoded pixels; 8-bit single-frame PNG only; Pillow extra.',
        text=str, width=int, height=int, mode=str, channel=str, bit=int, source_sha256=str,
        samples_sha256=str, coordinates=str, scope=str)]
