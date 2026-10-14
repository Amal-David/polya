"""An independent stdlib PNG producer; decoder is optional Pillow, never this encoder."""
import base64
import hashlib
import struct
import zlib

import pytest
from polya.artifact_png import png_bitplane


def png(width, height, raw, color=2, depth=8, palette=None):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind+data))
    channels = {0:1, 2:3, 3:1, 6:4}[color]
    stride = width*channels
    scanlines = b''.join(b'\0' + raw[i*stride:(i+1)*stride] for i in range(height))
    result = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, depth, color, 0, 0, 0))
    if palette is not None:
        result += chunk(b'PLTE', palette)
    return result + chunk(b'IDAT', zlib.compress(scanlines)) + chunk(b'IEND', b'')


def b64(raw):
    return base64.b64encode(raw).decode()


@pytest.mark.parametrize('bit', range(8))
@pytest.mark.parametrize('channel', ['R','G','B','A'])
def test_all_rgba_bitplanes_against_raw_samples(bit, channel):
    pytest.importorskip('PIL')
    raw = bytes(range(64))
    image = png(4, 4, raw, color=6)
    out = png_bitplane(b64(image), channel, bit)
    selected = raw[['R','G','B','A'].index(channel)::4]
    assert out['text'] == ''.join(str((x >> bit) & 1) for x in selected)
    assert out['source_sha256'] == hashlib.sha256(image).hexdigest()
    assert out['samples_sha256'] == hashlib.sha256(selected).hexdigest()
    assert out['width'] == out['height'] == 4


def test_palette_indices_are_not_silently_rgb_values():
    pytest.importorskip('PIL')
    image = png(2, 2, b'\0\1\1\0', color=3, palette=b'\xff\xff\xff\0\0\0')
    assert png_bitplane(b64(image), 'index', 0)['text'] == '0110'
    with pytest.raises(ValueError, match='no implicit conversion'):
        png_bitplane(b64(image), 'R', 0)


def test_unsupported_dimensions_and_depth_fail_before_decompression():
    image = png(1,1,b'\0\0\0')
    with pytest.raises(ValueError):
        png_bitplane(b64(image), 'R', True)
    too_large = bytearray(image); too_large[16:24] = struct.pack('>II', 20000,20000)
    with pytest.raises(ValueError, match='pixel budget'):
        png_bitplane(b64(too_large),'R',0)
    bad_depth = bytearray(image); bad_depth[24] = 16
    with pytest.raises(ValueError, match='8-bit'):
        png_bitplane(b64(bad_depth),'R',0)


def test_grayscale_exact_and_corruption_rejected():
    pytest.importorskip('PIL')
    image = png(2,2,bytes([0,255,2,3]),color=0)
    assert png_bitplane(b64(image),'L',0)['text'] == '0101'
    damaged = bytearray(image); damaged[-5] ^= 1
    with pytest.raises((ValueError, OSError)):
        png_bitplane(b64(damaged),'L',0)


def test_non_png_and_noncanonical_base64_rejected():
    for encoded in ['not base64', 'AAAA\n', b64(b'GIF89a'), b64(b'')]:
        with pytest.raises(ValueError):
            png_bitplane(encoded, 'R', 0)
