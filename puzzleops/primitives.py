"""Small exact transforms; no implicit cleanup, plaintext guessing, or I/O."""

from __future__ import annotations

import base64
import hashlib
import itertools
import math
import re
from collections import Counter
from decimal import Decimal, localcontext
from fractions import Fraction


MAX_BYTES = 65536


def from_hex(value: str) -> bytes:
    if not isinstance(value, str) or len(value) > MAX_BYTES * 2:
        raise ValueError("hex input exceeds 65536 bytes or is not text")
    if len(value) % 2 or re.fullmatch(r"[0-9a-fA-F]*", value) is None:
        raise ValueError("hex requires even length and no whitespace/prefix")
    return bytes.fromhex(value)


def bytes_decode(value: str, encoding: str) -> dict:
    if encoding == "hex":
        data = from_hex(value)
    elif encoding == "base64":
        try:
            data = base64.b64decode(value.encode("ascii"), validate=True)
        except (ValueError, UnicodeError) as exc:
            raise ValueError("expected strict, padded standard base64") from exc
        if base64.b64encode(data).decode("ascii") != value:
            raise ValueError("noncanonical base64; normalization must be explicit")
    else:
        raise ValueError("supported encodings: hex, base64")
    if len(data) > MAX_BYTES:
        raise ValueError("decoded output exceeds 65536 bytes")
    return {"hex": data.hex(), "byte_length": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), "encoding": encoding}


def text_profile(text: str) -> dict:
    counts = Counter(text)
    size = len(text)
    ioc = sum(v * (v - 1) for v in counts.values()) / (size * (size - 1)) if size > 1 else None
    entropy = -sum((n / size) * math.log2(n / size) for n in counts.values()) if size else 0.0
    dimensions = [[d, size // d] for d in range(1, math.isqrt(size) + 1) if size % d == 0]
    return {"codepoint_length": size, "utf8_byte_length": len(text.encode("utf-8")),
            "alphabet_size": len(counts), "counts": dict(sorted(counts.items())),
            "index_of_coincidence": ioc, "empirical_entropy_bits": entropy,
            "rectangular_dimensions": dimensions,
            "interpretation": "Descriptive statistics only; no cipher or hidden-message claim."}


def grid_read(text: str, rows: int, columns: int, order: str, reverse: bool = False) -> dict:
    if type(rows) is not int or type(columns) is not int or rows < 1 or columns < 1:
        raise ValueError("rows and columns must be positive integers")
    if len(text) != rows * columns:
        raise ValueError("grid dimensions must exactly equal Unicode codepoint length")
    if order == "row":
        offsets = list(range(len(text)))
    elif order == "column":
        offsets = [r * columns + c for c in range(columns) for r in range(rows)]
    elif order == "row_snake":
        offsets = [r * columns + c for r in range(rows)
                   for c in (range(columns) if r % 2 == 0 else range(columns - 1, -1, -1))]
    elif order == "column_snake":
        offsets = [r * columns + c for c in range(columns)
                   for r in (range(rows) if c % 2 == 0 else range(rows - 1, -1, -1))]
    else:
        raise ValueError("unsupported grid order")
    if reverse:
        offsets.reverse()
    return {"text": "".join(text[i] for i in offsets), "source_offsets": offsets,
            "unit": "Unicode codepoint", "rows": rows, "columns": columns,
            "order": order, "reverse": reverse}


def candidate_expand(slots: list[list[str]], separator: str = "", start: int = 0,
                     limit: int = 100) -> dict:
    if len(slots) > 32 or any(len(slot) > 10000 for slot in slots):
        raise ValueError("at most 32 slots with 10000 entries each")
    if type(start) is not int or start < 0 or type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("start >= 0 and 1 <= limit <= 1000 required")
    if any(any(not isinstance(x, str) for x in slot) for slot in slots):
        raise ValueError("slot entries must be strings")
    total = math.prod(len(slot) for slot in slots)
    if start > total:
        raise ValueError("start exceeds domain cardinality")
    if any(slot for slot in slots):
        max_length = sum(max(map(len, slot), default=0) for slot in slots) + max(0, len(slots)-1)*len(separator)
        if max_length * min(limit, max(0, total-start)) > 100000:
            raise ValueError("requested page exceeds 100000 output codepoints")
    candidates = []
    stop = min(total, start + limit)
    for index in range(start, stop):
        cursor = index
        coordinates = []
        for slot in reversed(slots):
            cursor, position = divmod(cursor, len(slot))
            coordinates.append(position)
        coordinates.reverse()
        values = [slot[position] for slot, position in zip(slots, coordinates)]
        candidates.append({"index": index, "choices": coordinates,
                           "parts": values, "text": separator.join(values)})
    return {"total_assignments": total, "start": start, "stop": stop,
            "emitted": len(candidates), "candidates": candidates,
            "next_start": stop if stop < total else None,
            "complete": start == 0 and stop == total,
            "status": "COMPLETE" if start == 0 and stop == total else "PARTIAL",
            "scope": "Ordered slot assignments; duplicate strings and their distinct derivations are preserved."}


def verify_sha256(candidate_hex: str, expected_sha256: str) -> dict:
    candidate = from_hex(candidate_hex)
    if re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256) is None:
        raise ValueError("expected_sha256 must contain exactly 64 hex digits")
    observed = hashlib.sha256(candidate).hexdigest()
    return {"match": observed == expected_sha256.lower(), "observed_sha256": observed,
            "expected_sha256": expected_sha256.lower(), "evidence_kind": "EXACT_COMMITMENT_CHECK",
            "scope": "SHA256 equality only; commitment provenance and puzzle interpretation are caller responsibilities."}


def padding_null(trials: int, block_bytes: int = 16, fixed_padding_bytes: int | None = None) -> dict:
    if type(trials) is not int or not 0 <= trials <= 10**18:
        raise ValueError("trials must be an integer in [0, 10^18]")
    if type(block_bytes) is not int or not 1 <= block_bytes <= 255:
        raise ValueError("block_bytes must be in [1, 255]")
    if fixed_padding_bytes is None:
        probability = sum((Fraction(1, 256**k) for k in range(1, block_bytes + 1)), Fraction(0))
    else:
        if type(fixed_padding_bytes) is not int or not 1 <= fixed_padding_bytes <= block_bytes:
            raise ValueError("fixed padding must be an integer within the block")
        probability = Fraction(1, 256**fixed_padding_bytes)
    expected = probability * trials
    with localcontext() as context:
        context.prec = 18
        probability_scientific = str(Decimal(probability.numerator) / Decimal(probability.denominator))
        expected_scientific = str(Decimal(expected.numerator) / Decimal(expected.denominator))
    return {"probability_numerator": str(probability.numerator),
            "probability_denominator": str(probability.denominator),
            "probability": float(probability), "trials": trials,
            "expected_padding_hits": float(expected),
            "probability_scientific": probability_scientific,
            "expected_padding_hits_scientific": expected_scientific,
            "float_underflow": float(probability) == 0.0 and probability > 0,
            "assumption": "Each wrong-key final block is uniformly random. Not an empirical p-value or a model of correlated search selection.",
            "evidence_kind": "NULL_EXPECTATION"}

