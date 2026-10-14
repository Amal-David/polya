"""Discoverable contracts and dispatch over the same native operations."""

from __future__ import annotations

from dataclasses import dataclass
import difflib
import hashlib
import json
from pathlib import Path
import platform
import re
import unicodedata
from threading import RLock
from importlib import metadata
from .runtime import execution_mode
from typing import Callable, Literal

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
    example: dict | None = None

    def contract(self):
        return {"operation_id": self.operation_id, "version": self.version,
                "title": self.title, "description": self.description,
                "input_schema": self.request.model_json_schema(),
                "output_schema": self.result.model_json_schema() if self.result else {"type": "object"},
                "postcondition": self.postcondition, "limits": self.limits,
                "cache_policy": "exact_request" if self.cacheable else "never", "example": self.example}


class ValidationError(ValueError):
    """Input rejection without model class names; named so error_type stays ValidationError."""


def _op(operation_id, title, description, request, kernel, terms, postcondition, limits, *, cacheable=True, example=None, **result_fields):
    result = output_model(operation_id.replace(".", "_") + "_result", **result_fields) if result_fields else None
    return Operation(operation_id, title, description, request, result, kernel, terms, postcondition, limits,
                     cacheable=cacheable, example=example)


OPS = [
    _op("bytes.decode", "Decode bytes", "Decode strict canonical base64 or hexadecimal.",
        DecodeInput, primitives.bytes_decode, "encoding base64 hex binary decode",
        "Exact bytes under the selected encoding; no whitespace repair or text guessing.", "65536 decoded bytes.",
        example={"value": "SGVsbG8=", "encoding": "base64"}, hex=str, byte_length=int, sha256=str, encoding=str),
    _op("text.profile", "Describe a symbol stream", "Return codepoint counts, empirical entropy, coincidence and grid dimensions.",
        TextInput, primitives.text_profile, "alphabet frequency entropy coincidence statistics symbols factor length",
        "Exact counts/dimensions; floating descriptive statistics. No interpretation is inferred.", "65536 codepoints.",
        example={"text": "ATTACKATDAWN"}, codepoint_length=int, utf8_byte_length=int, alphabet_size=int, counts=dict[str,int],
        index_of_coincidence=float|None, empirical_entropy_bits=float, rectangular_dimensions=list[list[int]], interpretation=str),
    _op("grid.read", "Read a rectangular text grid", "Reorder an exact rectangular grid while retaining source offsets.",
        GridInput, primitives.grid_read, "transposition columns rows snake boustrophedon extraction route grid reverse",
        "A permutation of source codepoints under the declared grid and reading order.", "65536 codepoints; no padding or truncation.",
        example={"text": "abcdef", "rows": 2, "columns": 3, "order": "column"}, text=str, source_offsets=list[int], unit=str, rows=int, columns=int, order=str, reverse=bool),
    _op("candidate.expand", "Page a finite candidate product", "Expand explicit slot alternatives with stable indices and complete derivation choices.",
        ExpandInput, primitives.candidate_expand, "cartesian candidate words product slots enumerate batch search space normalization",
        "Exactly the requested half-open index range of the ordered slot product. Duplicates preserved.",
        "32 slots, <=1000 outputs/page, 100000 output codepoints. Mixed-radix direct seeking.",
        example={"slots": [["red", "blue"], ["cat", "dog"]], "separator": " "}, total_assignments=int, start=int, stop=int, emitted=int, candidates=list[dict], next_start=int|None,
        complete=bool, status=Literal["COMPLETE","PARTIAL"], scope=str),
    _op("crypto.openssl_inspect", "Inspect legacy salted framing", "Recognize Salted__ with 8-byte salt and 16-byte-aligned ciphertext.",
        InspectInput, crypto.openssl_inspect, "openssl aes salt salted cipher kdf header inspect",
        "Framing only; cipher, key size, digest and KDF remain unknown.", "65536 bytes; legacy 8-byte-salt framing only.",
        format=str, salt_hex=str, ciphertext_hex=str, ciphertext_bytes=int, unknown_parameters=list[str], scope=str),
    _op("crypto.openssl_decrypt", "Evaluate an explicit AES password", "AES-256-CBC with legacy EVP_BytesToKey, count=1, explicit digest and password bytes.",
        DecryptInput, crypto.openssl_decrypt, "aes decrypt password openssl evp bytestokey md5 sha256 padding",
        "Deterministic decrypt under declared parameters. Padding is a signal, never a solution verdict.",
        "65536 blob bytes, 4096 password bytes. Not PBKDF2 or nonstandard CryptoJS Rijndael.",
        plaintext_padded_hex=str, plaintext_hex=str|None, padding_valid=bool, padding_bytes=int|None,
        cipher=str, kdf=str, iterations=int, digest=str, evidence_kind=str, scope=str),
    _op("crypto.bip39_seed", "Evaluate the BIP39 seed function", "NFKD + PBKDF2-HMAC-SHA512; vocabulary/checksum validation is a separate question.",
        SeedInput, crypto.bip39_seed, "bip39 mnemonic seed passphrase checksum unicode normalization nfkd pbkdf2",
        "Exact 64-byte seed-function output; does not certify a valid mnemonic or target address.", "8192 codepoints per field; 2048 iterations.",
        seed_hex=str, normalization=str, iterations=int, mnemonic_was_normalized=bool,
        passphrase_was_normalized=bool, checksum_checked=bool, vocabulary_checked=bool, scope=str),
    _op("verify.sha256", "Check a byte commitment", "Compare exact candidate bytes against a supplied SHA256 commitment.",
        VerifyInput, primitives.verify_sha256, "verify exact target commitment sha256 digest witness",
        "Digest equality under the provided commitment. Commitment provenance is not authenticated.", "65536 candidate bytes.",
        example={"candidate_hex": "616263", "expected_sha256": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"},
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
        example={"domains": {"a": ["0", "1"], "b": ["0", "1"]}, "constraints": [{"scope": ["a", "b"], "allowed": [["0", "1"], ["1", "0"]]}]},
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
from .crypto_targets import operations as target_ops
from .artifact_png import operations as png_ops
OPS.extend(target_ops(_op))
OPS.extend(png_ops(_op))
from .bitstreams import operations as bitstream_ops
from .plans import operations as plan_ops
OPS.extend(bitstream_ops(_op))
OPS.extend(plan_ops(_op))
from .jacobian_bridge import operations as jacobian_ops
OPS.extend(jacobian_ops(_op))
from .proposals import operations as proposal_ops
OPS.extend(proposal_ops(_op))
from .equality_patterns import operations as equality_ops
OPS.extend(equality_ops(_op))
REGISTRY = {op.operation_id: op for op in OPS}

# Pre-0.3.0 operation IDs, kept only so unknown-ID errors can point at the new name.
RENAMED_OPERATION_IDS = {
    "crypto.bip39.seed": "crypto.bip39_seed",
    "crypto.openssl.decrypt": "crypto.openssl_decrypt",
    "crypto.openssl.inspect": "crypto.openssl_inspect",
    "symbols.to_bits": "bits.from_symbols",
    "encoding.radix_bytes": "bytes.from_radix",
    "encoding.symbol_map": "text.symbol_map",
    "mechanism.scan": "mechanism.recipe_scan",
}


_STOPWORDS = frozenset({"a", "an", "and", "by", "in", "is", "of", "or", "the", "to", "with"})


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower())) - _STOPWORDS


def unknown_operation(operation_id) -> ValueError:
    renamed = RENAMED_OPERATION_IDS.get(operation_id) if type(operation_id) is str else None
    if renamed:
        return ValueError(f"unknown operation_id {operation_id!r}; renamed to {renamed!r} in 0.3.0")
    close = []
    if type(operation_id) is str:
        # A keyword hit on the name after the family catches synonyms (cipher.vigenere) that spelling misses.
        # An empty word set would make find() return every operation, so it gives no hint.
        name = " ".join(_words(operation_id.rpartition(".")[2].replace("_", " ")))
        keyword = [hit["operation_id"] for hit in find(name, limit=1)] if name else []
        close = (list(dict.fromkeys(keyword + difflib.get_close_matches(operation_id, REGISTRY, n=3, cutoff=0.5)))[:3]
                 or [known for known in REGISTRY if known.startswith(operation_id.partition(".")[0] + ".")])
    if close:
        return ValueError(f"unknown operation_id {operation_id!r}; did you mean {', '.join(close)}? Run 'polya list'.")
    return ValueError(f"unknown operation_id {operation_id!r}. Run 'polya list'.")


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def find(query: str = "", *, operation_id: str | None = None, limit: int = 5):
    if type(query) is not str or type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("query must be text and limit an integer in [1,100]")
    if operation_id is not None:
        if operation_id not in REGISTRY:
            raise unknown_operation(operation_id)
        return REGISTRY[operation_id].contract()
    tokens = _words(query)
    ranked = []
    for op in OPS:
        named, terms = _words(op.operation_id + " " + op.title), _words(op.terms)
        # A query word in the ID or title outranks one found only in the discovery terms.
        score = sum(2 if token in named else 1 if token in terms else 0 for token in tokens)
        if not tokens or score:
            ranked.append((score, op))
    ranked.sort(key=lambda item: (-item[0], item[1].operation_id))
    return [{"operation_id": op.operation_id, "title": op.title, "description": op.description,
             "postcondition": op.postcondition} for _, op in ranked[:limit]]


def _backend_versions():
    from importlib import metadata
    from .native_z3 import native_version
    versions = {"native_z3": native_version()}
    for name in ("ortools", "aalpy", "numpy", "protobuf", "Pillow"):
        try: versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError: versions[name] = None
    return versions


def _compute_implementation_fingerprint() -> str:
    """Bind receipts/cache to source and relevant runtime, including Unicode semantics."""
    digest = hashlib.sha256()
    digest.update(_SOURCE_SNAPSHOT)
    digest.update(b"jacobian-pinned-runtime\0" + _JACOBIAN_PIN_RUNTIME_SNAPSHOT)
    digest.update(canonical_json({"python": platform.python_version(), "package": __version__,
                                "cryptography": metadata.version("cryptography"), "pydantic": pydantic.__version__,
                                "unicode": unicodedata.unidata_version, "backends": _backend_versions()}).encode())
    return digest.hexdigest()


# Freeze source bytes now, not after a later on-disk edit. Native discovery is
# deferred until an experiment requests a receipt.
_SOURCE_SNAPSHOT = b"".join(path.name.encode("utf8") + b"\0" + path.read_bytes()
                            for path in sorted(Path(__file__).parent.glob("*.py")))


def _execution_pin_fields(value: dict) -> dict:
    # Do not churn receipt identity for a new observed upstream HEAD. Only a
    # promoted runtime/release changes the execution environment.
    return {name:value[name] for name in
            ("execution", "upstream", "version", "release_source_sha", "wheel_sha256", "requires_python")}


from .jacobian_bridge import pin as _jacobian_pin

_JACOBIAN_PIN_RUNTIME_SNAPSHOT = canonical_json(_execution_pin_fields(_jacobian_pin())).encode("utf8")
_FINGERPRINT_LOCK = RLock()
_LOADED_FINGERPRINT = None
_FINGERPRINT_GENERATION = None


def implementation_fingerprint() -> str:
    global _LOADED_FINGERPRINT, _FINGERPRINT_GENERATION
    from .native_z3 import library_generation
    generation = library_generation()
    with _FINGERPRINT_LOCK:
        if _LOADED_FINGERPRINT is None or _FINGERPRINT_GENERATION != generation:
            _LOADED_FINGERPRINT = _compute_implementation_fingerprint()
            _FINGERPRINT_GENERATION = generation
        base = _LOADED_FINGERPRINT
    return hashlib.sha256((base + canonical_json(execution_mode())).encode("utf8")).hexdigest()


def prepare(operation_id: str, inputs: dict):
    if operation_id not in REGISTRY:
        raise unknown_operation(operation_id)
    if type(inputs) is not dict:
        raise ValueError("inputs must be an object")
    if len(canonical_json(inputs)) > 1_000_000:
        raise ValueError("input JSON exceeds 1 MB prototype admission limit")
    op = REGISTRY[operation_id]
    try:
        validated = op.request.model_validate(inputs).model_dump(mode="json")
    except pydantic.ValidationError as exc:
        raise ValidationError(f"invalid inputs for {operation_id}: " + "; ".join(
            f"{'.'.join(map(str, error['loc'])) or 'inputs'}: {error['msg']}" for error in exc.errors())) from exc
    identity = {"operation_id": operation_id, "operation_version": op.version,
                "implementation": implementation_fingerprint(), "inputs": validated,
                "runtime_mode": execution_mode()}
    key = hashlib.sha256(canonical_json(identity).encode()).hexdigest()
    return op, validated, identity, key


def execute_prepared(op, validated, identity, key):
    result = op.kernel(**validated)
    if op.result:
        result = op.result.model_validate(result).model_dump(mode="json")
    if len(canonical_json(result).encode("utf8")) > 1_000_000:
        raise ValueError("result exceeds 1 MB output admission limit; reduce the requested scope")
    # Lazy native imports may change interpreter mode during the kernel. These
    # are boundary observations, not a claim of continuous process monitoring.
    after = execution_mode()
    final_fingerprint = (implementation_fingerprint()
                         if after != identity["runtime_mode"] else identity["implementation"])
    return {"operation_id": op.operation_id, "result": result,
            "receipt": make_receipt(op, validated, identity, key, result,
                                    runtime_after=after, final_fingerprint=final_fingerprint)}


def make_receipt(op, validated, identity, key, result, *, runtime_after=None, final_fingerprint=None):
    result_hash = hashlib.sha256(canonical_json(result).encode()).hexdigest()
    before = identity["runtime_mode"]
    after = before if runtime_after is None else runtime_after
    return {"experiment_key": key,
                        "implementation_fingerprint": final_fingerprint or identity["implementation"],
                        "preparation_implementation_fingerprint": identity["implementation"],
                        "runtime_observations": {"before": before, "after": after,
                                                 "changed": before != after,
                                                 "scope": "Boundary samples, not continuous runtime monitoring."},
                        "operation_version": op.version, "inputs_sha256": hashlib.sha256(canonical_json(validated).encode()).hexdigest(),
                        "result_sha256": result_hash, "postcondition": op.postcondition,
                        "independently_reproduced": False,
                        "scope": "Execution receipt; not a proof of puzzle interpretation or a cryptographic attestation."}


def run(operation_id: str, inputs: dict):
    return execute_prepared(*prepare(operation_id, inputs))
