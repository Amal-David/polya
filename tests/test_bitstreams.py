"""Independent byte fixtures, strict admission, and provenance for bitstreams."""
import importlib
from itertools import product

import pytest

from polya import find, run
from polya.bitstreams import (MAX_BITS, MAX_SLICE_BYTES, InvertSpec, PackSpec,
                              SliceSpec, SymbolsSpec, invert_bits, operations,
                              pack_bits, slice_bytes, symbols_to_bits)
from polya.catalog import _op, canonical_json
from polya.cryptic import radix_bytes


def test_module_is_shared():
    assert importlib.import_module("polya.bitstreams") is importlib.import_module("puzzleops.bitstreams")


@pytest.mark.parametrize("width", range(9))
def test_inversion_exhaustive_small_inputs(width):
    for symbols in product("01", repeat=width):
        text = "".join(symbols)
        unchanged = invert_bits(text)
        inverted = invert_bits(text, True)
        assert unchanged["text"] == text
        assert inverted["text"] == "".join(str(1 - int(bit)) for bit in text)
        assert unchanged["source_offsets"] == inverted["source_offsets"] == list(range(width))


@pytest.mark.parametrize("bit_order", ["msb", "lsb"])
def test_packing_all_byte_values_against_independent_bytes_fixture(bit_order):
    expected = bytes(range(256))
    shifts = range(7, -1, -1) if bit_order == "msb" else range(8)
    bits = "".join(str((value >> shift) & 1) for value in expected for shift in shifts)
    result = pack_bits(bits, bit_order)
    assert result["hex"] == expected.hex()
    assert result["byte_length"] == 256
    assert result["consumed_bits"] == 2048
    assert result["dropped_offsets"] == []
    assert result["bit_order"] == bit_order
    assert result["tail"] == "reject"
    for value, offsets in zip(expected, result["source_offsets"]):
        # Reconstruct using independent arithmetic, following the provenance.
        assert sum((bits[index] == "1") * (128 >> significance)
                   for significance, index in enumerate(offsets)) == value
        expected_offsets = list(range(value * 8, (value + 1) * 8))
        assert offsets == (expected_offsets if bit_order == "msb" else expected_offsets[::-1])


def test_leading_zero_bytes_and_lsb_order_are_preserved():
    bits = "00000000000000001000000101000000"
    msb = pack_bits(bits)
    lsb = pack_bits(bits, "lsb")
    assert msb["hex"] == "00008140"
    assert lsb["hex"] == "00008102"
    assert msb["byte_length"] == lsb["byte_length"] == 4
    assert msb["source_offsets"][-1] == [24, 25, 26, 27, 28, 29, 30, 31]
    assert lsb["source_offsets"][-1] == [31, 30, 29, 28, 27, 26, 25, 24]


@pytest.mark.parametrize("bit_order,tail", list(product(["msb", "lsb"], ["reject", "drop"])))
def test_empty_binary_stream(bit_order, tail):
    result = pack_bits("", bit_order, tail)
    assert result["hex"] == ""
    assert result["byte_length"] == result["consumed_bits"] == 0
    assert result["source_offsets"] == result["dropped_offsets"] == []
    assert result["bit_order"] == bit_order and result["tail"] == tail


@pytest.mark.parametrize("remainder", range(1, 8))
@pytest.mark.parametrize("bit_order", ["msb", "lsb"])
def test_every_partial_tail_is_explicit(remainder, bit_order):
    text = "10000000" + "1" * remainder
    with pytest.raises(ValueError, match="incomplete trailing byte"):
        pack_bits(text, bit_order)
    result = pack_bits(text, bit_order, "drop")
    assert result["hex"] == ("80" if bit_order == "msb" else "01")
    assert result["consumed_bits"] == 8
    assert result["dropped_offsets"] == list(range(8, 8 + remainder))
    short = pack_bits("1" * remainder, bit_order, "drop")
    assert short["hex"] == "" and short["source_offsets"] == []
    assert short["consumed_bits"] == 0 and short["byte_length"] == 0
    assert short["dropped_offsets"] == list(range(remainder))


@pytest.mark.parametrize("text", ["2", "010 101", "00000000\n", "00000000x", "０１", "01\x00", "0b01", "+1"])
def test_binary_inputs_never_normalize_even_dropped_tails(text):
    with pytest.raises(ValueError):
        invert_bits(text)
    with pytest.raises(ValueError):
        pack_bits(text, tail="drop")


def test_symbol_mapping_uses_code_points_and_explicit_whitespace():
    result = symbols_to_bits("🌑☀🌑☀☀", zero="🌑", one="☀")
    assert result["text"] == "01011"
    assert result["source_offsets"] == [0, 1, 2, 3, 4]
    assert symbols_to_bits(" \n  \n", zero=" ", one="\n")["text"] == "01001"
    assert symbols_to_bits("", zero="a", one="b")["source_offsets"] == []
    assert symbols_to_bits("e\u0301", zero="e", one="\u0301")["text"] == "01"
    with pytest.raises(ValueError):
        symbols_to_bits("é", zero="e", one="\u0301")


@pytest.mark.parametrize("text,zero,one", [
    ("", "a", "a"), ("a", "", "a"), ("ab", "ab", "c"),
    ("e\u0301", "e\u0301", "x"), ("a b", "a", "b"),
    ("A", "a", "b"), ("01", "0", "10"), ("", "0", ""),
])
def test_symbol_mapping_rejects_ambiguous_or_unmapped_sources(text, zero, one):
    with pytest.raises(ValueError):
        symbols_to_bits(text, zero, one)


@pytest.mark.parametrize("bad", [True, False, 0, 1, None, b"01", ["0", "1"]])
def test_text_is_strictly_a_string(bad):
    for call in (lambda: invert_bits(bad), lambda: pack_bits(bad),
                 lambda: symbols_to_bits(bad, "0", "1"), lambda: slice_bytes(bad, 0, 0)):
        with pytest.raises(ValueError):
            call()


@pytest.mark.parametrize("bad", [0, 1, "true", "false", None])
def test_inversion_requires_a_real_boolean(bad):
    with pytest.raises(ValueError):
        invert_bits("01", bad)


@pytest.mark.parametrize("bad", [True, False, 0, "MSB", "big", "", None])
def test_bit_order_is_explicit(bad):
    with pytest.raises(ValueError):
        pack_bits("00000000", bit_order=bad)


@pytest.mark.parametrize("bad", [True, False, 0, "report", "pad", "", None])
def test_tail_policy_is_explicit(bad):
    with pytest.raises(ValueError):
        pack_bits("00000000", tail=bad)


def test_maximum_binary_size_matches_png_without_changing_radix_limits():
    bits = "0000000011111111" * (MAX_BITS // 16)
    inverted = invert_bits(bits, True)
    mapped = symbols_to_bits("🌑☀" * (MAX_BITS // 2), "🌑", "☀")
    packed = pack_bits(bits)
    assert len(inverted["text"]) == len(mapped["text"]) == MAX_BITS
    assert inverted["source_offsets"][-1] == mapped["source_offsets"][-1] == MAX_BITS - 1
    assert packed["hex"] == "00ff" * (MAX_BITS // 16)
    assert packed["byte_length"] == 8192
    assert packed["source_offsets"][-1] == list(range(MAX_BITS - 8, MAX_BITS))
    assert packed["consumed_bits"] == MAX_BITS
    for result in (inverted, mapped, packed):
        assert len(canonical_json(result).encode("utf-8")) < 1_000_000
    for call in (lambda: invert_bits("0" * (MAX_BITS + 1)),
                 lambda: pack_bits("0" * (MAX_BITS + 1), tail="drop"),
                 lambda: symbols_to_bits("x" * (MAX_BITS + 1), "x", "y")):
        with pytest.raises(ValueError):
            call()
    assert radix_bytes("0" * 2048, 2, mode="groups")["byte_count"] == 256
    with pytest.raises(ValueError, match="2048"):
        radix_bytes("0" * 2049, 2, mode="groups", tail="report")


@pytest.mark.parametrize("start,stop", [(0, 256), (0, 0), (256, 256), (1, 255), (42, 42), (0, 1), (255, 256)])
def test_byte_slice_against_independent_fixture_and_loss_accounting(start, stop):
    source = bytes(range(256))
    result = slice_bytes(source.hex().upper(), start, stop)
    assert result["hex"] == source[start:stop].hex()
    assert result["byte_length"] == stop - start
    assert result["source_offsets"] == list(range(start, stop))
    assert result["dropped_ranges"] == ([[0, start]] if start else []) + ([[stop, 256]] if stop < 256 else [])
    dropped = [index for begin, end in result["dropped_ranges"] for index in range(begin, end)]
    assert sorted(result["source_offsets"] + dropped) == list(range(256))
    assert all(begin < end for begin, end in result["dropped_ranges"])


def test_empty_and_maximum_byte_slices_and_explicit_password_selection():
    empty = slice_bytes("", 0, 0)
    assert empty["hex"] == "" and empty["source_offsets"] == empty["dropped_ranges"] == []
    raw = bytes(range(256)) * (MAX_SLICE_BYTES // 256)
    full = slice_bytes(raw.hex(), 0, len(raw))
    assert full["hex"] == raw.hex() and full["byte_length"] == MAX_SLICE_BYTES
    assert full["source_offsets"] == list(range(MAX_SLICE_BYTES))
    assert full["dropped_ranges"] == []
    packed = pack_bits("0" * MAX_BITS)
    selected = slice_bytes(packed["hex"], 0, 4096)
    assert selected["byte_length"] == 4096
    assert selected["dropped_ranges"] == [[4096, 8192]]
    with pytest.raises(ValueError):
        slice_bytes("00" * (MAX_SLICE_BYTES + 1), 0, 0)


@pytest.mark.parametrize("value_hex,start,stop", [
    ("0", 0, 0), ("00 ", 0, 1), ("00\n", 0, 1), ("0x00", 0, 1),
    ("gg", 0, 1), ("００", 0, 1), ("00", -1, 1), ("00", 0, -1),
    ("00", 1, 0), ("00", 0, 2), ("", 0, 1), ("00", True, 1),
    ("00", 0, False), ("00", "0", 1), ("00", 0, 1.0),
])
def test_byte_slice_rejects_invalid_hex_and_out_of_range_or_coerced_indices(value_hex, start, stop):
    with pytest.raises(ValueError):
        slice_bytes(value_hex, start, stop)


def test_request_models_forbid_extra_fields_and_require_explicit_selection():
    for spec, payload in ((InvertSpec, {"text": ""}), (PackSpec, {"text": ""}),
                          (SymbolsSpec, {"text": "", "zero": "a", "one": "b"}),
                          (SliceSpec, {"value_hex": "", "start": 0, "stop": 0})):
        with pytest.raises(ValueError):
            spec.model_validate({**payload, "extra": True})
    with pytest.raises(ValueError):
        SliceSpec.model_validate({"value_hex": "00", "start": 0})
    for zero, one in ((0, "1"), ("0", 1), (True, "1"), ("0", b"1")):
        with pytest.raises(ValueError):
            SymbolsSpec(text="", zero=zero, one=one)


def test_declared_contract_limits_and_strict_output_models():
    contracts = {operation.operation_id: operation for operation in operations(_op)}
    assert set(contracts) == {"bits.invert", "bits.pack", "symbols.to_bits", "bytes.slice"}
    for operation in contracts.values():
        contract = operation.contract()
        assert contract["input_schema"]["additionalProperties"] is False
        assert contract["output_schema"]["additionalProperties"] is False
        assert "65536" in contract["limits"] or "32768" in contract["limits"]
    for name in ("bits.invert", "bits.pack", "symbols.to_bits"):
        schema = contracts[name].contract()["input_schema"]
        assert schema["properties"]["text"]["maxLength"] == MAX_BITS
    packed = contracts["bits.pack"]
    schema = packed.contract()["output_schema"]["properties"]
    assert schema["source_offsets"]["maxItems"] == 8192
    assert schema["source_offsets"]["items"]["minItems"] == 8
    assert schema["dropped_offsets"]["maxItems"] == 7
    with pytest.raises(ValueError):
        packed.result.model_validate({**pack_bits(""), "byte_length": False})
    with pytest.raises(ValueError):
        packed.result.model_validate({**pack_bits("00000000"), "source_offsets": [[0]]})


@pytest.mark.parametrize("operation_id,payload,expected", [
    ("bits.invert", {"text": "001", "invert": True}, "110"),
    ("bits.pack", {"text": "0000000011111111"}, "00ff"),
    ("symbols.to_bits", {"text": "aabba", "zero": "a", "one": "b"}, "00110"),
    ("bytes.slice", {"value_hex": "00ff80", "start": 1, "stop": 3}, "ff80"),
])
def test_public_dispatch_discovery_and_receipts(operation_id, payload, expected):
    contract = find(operation_id=operation_id)
    assert contract["cache_policy"] == "exact_request"
    result = run(operation_id, payload)
    assert result["result"].get("text", result["result"].get("hex")) == expected
    assert result["receipt"]["independently_reproduced"] is False
    with pytest.raises(ValueError):
        run(operation_id, {**payload, "extra": True})
