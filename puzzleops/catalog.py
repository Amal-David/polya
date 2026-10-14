"""Discoverable contracts and dispatch over the same native operations."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import platform
import re
import unicodedata
from typing import Callable, Literal

import cryptography
import pydantic
from pydantic import BaseModel, ConfigDict, Field, create_model

from . import __version__, crypto, primitives
from .constraints import plan_factors, solve_tables


class Contract(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class DecodeInput(Contract):
    value: str = Field(max_length=131072)
    encoding: Literal["hex", "base64"]


class TextInput(Contract):
    text: str = Field(max_length=65536)


class GridInput(TextInput):
    rows: int = Field(ge=1, le=65536)
    columns: int = Field(ge=1, le=65536)
    order: Literal["row", "column", "row_snake", "column_snake"]
    reverse: bool = False


class ExpandInput(Contract):
    slots: list[list[str]] = Field(max_length=32)
    separator: str = Field(default="", max_length=1024)
    start: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=1000)


class InspectInput(Contract):
    blob_hex: str = Field(max_length=131072)


class DecryptInput(InspectInput):
    password_hex: str = Field(max_length=8192)
    digest: Literal["md5", "sha256"]


class SeedInput(Contract):
    mnemonic: str = Field(max_length=8192)
    passphrase: str = Field(max_length=8192)


class VerifyInput(Contract):
    candidate_hex: str = Field(max_length=131072)
    expected_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")


class PaddingInput(Contract):
    trials: int = Field(ge=0, le=10**18)
    block_bytes: int = Field(default=16, ge=1, le=255)
    fixed_padding_bytes: int | None = Field(default=None, ge=1, le=255)


class PlanInput(Contract):
    domains: dict[str, list[str]]
    scopes: list[list[str]]


class Table(Contract):
    scope: list[str]
    allowed: list[list[str]]


class SolveInput(Contract):
    domains: dict[str, list[str]]
    constraints: list[Table]
    max_solutions: int = Field(default=100, ge=1, le=10000)
    max_nodes: int = Field(default=100000, ge=1, le=1000000)


class FactorComponent(Contract):
    variables: list[str]
    factor_indices: list[int]
    joint_assignments: int


def output_model(name: str, **fields):
    return create_model(name, __base__=Contract, **{key: (kind, ...) for key, kind in fields.items()})


@dataclass(frozen=True)
class Operation:
    operation_id: str
    title: str
    description: str
    request: type[Contract]
    result: type[Contract] | None
    kernel: Callable
    terms: str
    postcondition: str
    limits: str
    version: str = "1"
    cacheable: bool = True

    def contract(self):
        return {"operation_id": self.operation_id, "version": self.version,
                "title": self.title, "description": self.description,
                "input_schema": self.request.model_json_schema(),
                "output_schema": self.result.model_json_schema() if self.result else {"type": "object"},
                "postcondition": self.postcondition, "limits": self.limits,
                "cache_policy": "exact_request" if self.cacheable else "never"}


def _op(operation_id, title, description, request, kernel, terms, postcondition, limits, *, cacheable=True, **result_fields):
    result = output_model(operation_id.replace(".", "_") + "_result", **result_fields) if result_fields else None
    return Operation(operation_id, title, description, request, result, kernel, terms, postcondition, limits, cacheable=cacheable)


OPS = [
    _op("bytes.decode", "Decode bytes", "Decode strict canonical base64 or hexadecimal.",
        DecodeInput, primitives.bytes_decode, "encoding base64 hex binary decode",
        "Exact bytes under the selected encoding; no whitespace repair or text guessing.", "65536 decoded bytes.",
        hex=str, byte_length=int, sha256=str, encoding=str),
    _op("text.profile", "Describe a symbol stream", "Return codepoint counts, empirical entropy, coincidence and grid dimensions.",
        TextInput, primitives.text_profile, "alphabet frequency entropy coincidence statistics symbols factor length",
        "Exact counts/dimensions; floating descriptive statistics. No interpretation is inferred.", "65536 codepoints.",
        codepoint_length=int, utf8_byte_length=int, alphabet_size=int, counts=dict[str,int],
        index_of_coincidence=float|None, empirical_entropy_bits=float, rectangular_dimensions=list[list[int]], interpretation=str),
    _op("grid.read", "Read a rectangular text grid", "Reorder an exact rectangular grid while retaining source offsets.",
        GridInput, primitives.grid_read, "transposition columns rows snake boustrophedon extraction route grid reverse",
        "A permutation of source codepoints under the declared grid and reading order.", "65536 codepoints; no padding or truncation.",
        text=str, source_offsets=list[int], unit=str, rows=int, columns=int, order=str, reverse=bool),
    _op("candidate.expand", "Page a finite candidate product", "Expand explicit slot alternatives with stable indices and complete derivation choices.",
        ExpandInput, primitives.candidate_expand, "cartesian candidate words product slots enumerate batch search space normalization",
        "Exactly the requested half-open index range of the ordered slot product. Duplicates preserved.",
        "32 slots, <=1000 outputs/page, 100000 output codepoints. Mixed-radix direct seeking.",
        total_assignments=int, start=int, stop=int, emitted=int, candidates=list[dict], next_start=int|None,
        complete=bool, status=Literal["COMPLETE","PARTIAL"], scope=str),
    _op("crypto.openssl.inspect", "Inspect legacy salted framing", "Recognize Salted__ with 8-byte salt and 16-byte-aligned ciphertext.",
        InspectInput, crypto.openssl_inspect, "openssl aes salt salted cipher kdf header inspect",
        "Framing only; cipher, key size, digest and KDF remain unknown.", "65536 bytes; legacy 8-byte-salt framing only.",
        format=str, salt_hex=str, ciphertext_hex=str, ciphertext_bytes=int, unknown_parameters=list[str], scope=str),
    _op("crypto.openssl.decrypt", "Evaluate an explicit AES password", "AES-256-CBC with legacy EVP_BytesToKey, count=1, explicit digest and password bytes.",
        DecryptInput, crypto.openssl_decrypt, "aes decrypt password openssl evp bytestokey md5 sha256 padding",
        "Deterministic decrypt under declared parameters. Padding is a signal, never a solution verdict.",
        "65536 blob bytes, 4096 password bytes. Not PBKDF2 or nonstandard CryptoJS Rijndael.",
        plaintext_padded_hex=str, plaintext_hex=str|None, padding_valid=bool, padding_bytes=int|None,
        cipher=str, kdf=str, iterations=int, digest=str, evidence_kind=str, scope=str),
    _op("crypto.bip39.seed", "Evaluate the BIP39 seed function", "NFKD + PBKDF2-HMAC-SHA512; vocabulary/checksum validation is a separate question.",
        SeedInput, crypto.bip39_seed, "bip39 mnemonic seed passphrase checksum unicode normalization nfkd pbkdf2",
        "Exact 64-byte seed-function output; does not certify a valid mnemonic or target address.", "8192 codepoints per field; 2048 iterations.",
        seed_hex=str, normalization=str, iterations=int, mnemonic_was_normalized=bool,
        passphrase_was_normalized=bool, checksum_checked=bool, vocabulary_checked=bool, scope=str),
    _op("verify.sha256", "Check a byte commitment", "Compare exact candidate bytes against a supplied SHA256 commitment.",
        VerifyInput, primitives.verify_sha256, "verify exact target commitment sha256 digest witness",
        "Digest equality under the provided commitment. Commitment provenance is not authenticated.", "65536 candidate bytes.",
        match=bool, observed_sha256=str, expected_sha256=str, evidence_kind=str, scope=str),
    _op("evidence.padding_null", "Compute chance padding expectation", "Expected padding hits under a uniform wrong-key final-block model.",
        PaddingInput, primitives.padding_null, "padding false positive negative controls null expectation statistics pkcs7 chance",
        "Exact rational event probability and floating expected count under a declared null; not a significance test.", "<=10^18 trials; block size <=255 bytes.",
        probability_numerator=str, probability_denominator=str, probability=float, trials=int,
        expected_padding_hits=float, probability_scientific=str,
        expected_padding_hits_scientific=str, float_underflow=bool, assumption=str, evidence_kind=str),
    _op("constraints.plan", "Plan declared local factors", "Count product and local-factor work; report connected components.",
        PlanInput, plan_factors, "constraint factorization pair independent graph components search cost budget",
        "Counts for caller-supplied domains and factor scopes. Does not establish real-puzzle independence.",
        "Counts only; no evaluation. Survivor joins still add work.",
        joint_assignments=int, factor_local_combinations=list[int], sum_factor_local_combinations=int,
        components=list[FactorComponent], zero_arity_factors=list[int], assumption_notice=str),
    _op("constraints.solve", "Solve a finite table constraint system", "Propagate explicit allowed tables and enumerate assignments under budgets.",
        SolveInput, solve_tables, "constraint join table csp solve finite domain arc semijoin pruning factor",
        "Solutions of the declared table system only; COMPLETE empty output rejects that system, not the puzzle.",
        "Explicit node/result/propagation/output budgets and admission limits; PARTIAL never means unsatisfiable.",
        status=Literal["COMPLETE","PARTIAL"], complete=bool, solutions=list[dict[str,str]], nodes_visited=int,
        termination_reason=Literal["exhausted","solution_limit","node_limit","propagation_limit","output_limit"],
        propagation_checks=int, propagation_check_limit=int, output_bytes=int, output_byte_limit=int, exact_scope=str),
]
from .extensions import extension_ops
OPS.extend(extension_ops(_op))
from .cryptic import operations as cryptic_ops
from .mechanisms import operations as mechanism_ops
OPS.extend(cryptic_ops(_op))
OPS.extend(mechanism_ops(_op))
REGISTRY = {op.operation_id: op for op in OPS}


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def find(query: str = "", *, operation_id: str | None = None, limit: int = 5):
    if type(query) is not str or type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("query must be text and limit an integer in [1,20]")
    if operation_id is not None:
        if operation_id not in REGISTRY:
            raise ValueError("unknown operation_id")
        return REGISTRY[operation_id].contract()
    tokens = set(re.findall(r"[a-z0-9]+", query.lower()))
    ranked = []
    for op in OPS:
        fields = (op.operation_id + " " + op.title + " " + op.terms).lower()
        score = sum(1 for token in tokens if token in re.findall(r"[a-z0-9]+", fields))
        if not tokens or score:
            ranked.append((score, op))
    ranked.sort(key=lambda item: (-item[0], item[1].operation_id))
    return [{"operation_id": op.operation_id, "title": op.title, "description": op.description,
             "postcondition": op.postcondition} for _, op in ranked[:limit]]


def _backend_versions():
    from importlib import metadata
    from .native_z3 import native_version
    versions = {"native_z3": native_version()}
    for name in ("ortools", "aalpy", "numpy", "protobuf"):
        try: versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError: versions[name] = None
    return versions


def _compute_implementation_fingerprint() -> str:
    """Bind receipts/cache to source and relevant runtime, including Unicode semantics."""
    digest = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        digest.update(path.name.encode("utf8")); digest.update(path.read_bytes())
    digest.update(canonical_json({"python": platform.python_version(), "package": __version__,
                                "cryptography": cryptography.__version__, "pydantic": pydantic.__version__,
                                "unicode": unicodedata.unidata_version, "backends": _backend_versions()}).encode())
    return digest.hexdigest()


_LOADED_FINGERPRINT = _compute_implementation_fingerprint()


def implementation_fingerprint() -> str:
    # Bind to the code loaded in this process, not a later edit of its source files.
    return _LOADED_FINGERPRINT


def prepare(operation_id: str, inputs: dict):
    if operation_id not in REGISTRY:
        raise ValueError("unknown operation_id")
    if type(inputs) is not dict:
        raise ValueError("inputs must be an object")
    if len(canonical_json(inputs)) > 1_000_000:
        raise ValueError("input JSON exceeds 1 MB prototype admission limit")
    op = REGISTRY[operation_id]
    validated = op.request.model_validate(inputs).model_dump(mode="json")
    identity = {"operation_id": operation_id, "operation_version": op.version,
                "implementation": implementation_fingerprint(), "inputs": validated}
    key = hashlib.sha256(canonical_json(identity).encode()).hexdigest()
    return op, validated, identity, key


def execute_prepared(op, validated, identity, key):
    result = op.kernel(**validated)
    if op.result:
        result = op.result.model_validate(result).model_dump(mode="json")
    if len(canonical_json(result).encode("utf8")) > 1_000_000:
        raise ValueError("result exceeds 1 MB output admission limit; reduce the requested scope")
    return {"operation_id": op.operation_id, "result": result,
            "receipt": make_receipt(op, validated, identity, key, result)}


def make_receipt(op, validated, identity, key, result):
    result_hash = hashlib.sha256(canonical_json(result).encode()).hexdigest()
    return {"experiment_key": key, "implementation_fingerprint": identity["implementation"],
                        "operation_version": op.version, "inputs_sha256": hashlib.sha256(canonical_json(validated).encode()).hexdigest(),
                        "result_sha256": result_hash, "postcondition": op.postcondition,
                        "independently_reproduced": False,
                        "scope": "Execution receipt; not a proof of puzzle interpretation or a cryptographic attestation."}


def run(operation_id: str, inputs: dict):
    return execute_prepared(*prepare(operation_id, inputs))
