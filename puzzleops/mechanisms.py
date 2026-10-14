"""Finite decoding-recipe search with explicit choices and shared-prefix reuse.

This searches caller-declared recipes, not arbitrary code or an unlimited space
of interpretations. Checkpoints filter results; they are never called solutions.
"""
from __future__ import annotations

import hashlib
import json
from math import prod
import time
from typing import Literal

from pydantic import Field, ValidationError
from .cryptic import Spec, MAX_TEXT

# Only deterministic string-to-string operations. No recursion, file or network
# tools, model execution, random sampling, or caller-provided executable code.
ALLOWED = frozenset({"grid.traverse", "encoding.symbol_map", "encoding.radix_bytes",
    "cipher.polyalphabetic", "cipher.bifid", "cipher.checkerboard",
    "bytes.decode", "crypto.openssl.decrypt"})


class Step(Spec):
    operation_id: str = Field(min_length=1, max_length=80)
    input_field: str = Field(min_length=1, max_length=80)
    output_field: str = Field(min_length=1, max_length=80)
    inputs: dict = Field(default_factory=dict)
    rationale: str = Field(min_length=1, max_length=512)


class Checkpoint(Spec):
    kind: Literal["equals", "prefix", "sha256"]
    value: str = Field(min_length=1, max_length=MAX_TEXT)
    source: str = Field(min_length=1, max_length=512)


class ScanSpec(Spec):
    source: str = Field(max_length=MAX_TEXT)
    stages: list[list[Step]] = Field(min_length=1, max_length=6)
    checkpoint: Checkpoint
    start: int = Field(default=0, ge=0)
    max_trials: int = Field(default=256, ge=1, le=512)
    max_matches: int = Field(default=8, ge=1, le=16)
    max_work: int = Field(default=500000, ge=1, le=2000000)
    timeout_ms: int = Field(default=5000, ge=1, le=60000)


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _indexes(ordinal: int, sizes: list[int]) -> list[int]:
    indexes = []
    for size in reversed(sizes):
        ordinal, i = divmod(ordinal,size); indexes.append(i)
    return indexes[::-1]


def scan(source: str, stages: list[list[dict]], checkpoint: dict, start: int = 0,
         max_trials: int = 256, max_matches: int = 8, max_work: int = 500000,
         timeout_ms: int = 5000) -> dict:
    from .catalog import REGISTRY
    p = ScanSpec(source=source, stages=stages, checkpoint=checkpoint, start=start,
                 max_trials=max_trials, max_matches=max_matches, max_work=max_work, timeout_ms=timeout_ms)
    sizes = [len(stage) for stage in p.stages]
    if any(not 1 <= size <= 64 for size in sizes) or prod(sizes) > 1000000:
        raise ValueError("1..64 alternatives per stage, at most one million declared recipes")
    total = prod(sizes)
    if start > total:
        raise ValueError("start is outside the declared recipe space")
    if len(_json(stages)) > 100000:
        raise ValueError("recipe definitions exceed 100000 characters")
    for stage in p.stages:
        for step in stage:
            if step.operation_id not in ALLOWED:
                raise ValueError("operation is not in the deterministic recipe allowlist")
            operation = REGISTRY[step.operation_id]
            if step.input_field in step.inputs:
                raise ValueError("bound input field must not also be supplied as a constant")
            if step.input_field not in operation.request.model_fields:
                raise ValueError("unknown bound input field")
            if step.output_field not in operation.result.model_fields:
                raise ValueError("unknown selected output field")
            if set(step.inputs) - operation.request.model_fields.keys():
                raise ValueError("unknown constant input field")
    if p.checkpoint.kind == "sha256":
        try:
            if len(p.checkpoint.value)!=64 or len(bytes.fromhex(p.checkpoint.value))!=32:
                raise ValueError()
        except ValueError as exc:
            raise ValueError("sha256 checkpoint must have exactly 64 hexadecimal characters") from exc
    def matches(text):
        if p.checkpoint.kind == "equals":
            return text == p.checkpoint.value
        if p.checkpoint.kind == "prefix":
            return text.startswith(p.checkpoint.value)
        return hashlib.sha256(text.encode("utf-8")).hexdigest() == p.checkpoint.value.lower()
    cache = {}
    cache_chars = kernel_calls = cache_hits = work = 0
    trials, hits = [], []
    deadline = time.monotonic()+timeout_ms/1000
    cursor, reason = start, "recipe_limit"
    stop = min(total, start+max_trials)
    while cursor < stop:
        indexes = _indexes(cursor, sizes)
        text, trace, error, paused = source, [], None, False
        for stage_index, choice in enumerate(indexes):
            if time.monotonic() >= deadline:
                reason, paused = "time_limit", True; break
            step = p.stages[stage_index][choice]
            args = dict(step.inputs); args[step.input_field] = text
            key = (step.operation_id, step.output_field, _json(args))
            if key in cache:
                output, info, error = cache[key]; cache_hits += 1
            else:
                operation = REGISTRY[step.operation_id]
                output = None; info = {}; inputs = None
                try:
                    inputs = operation.request.model_validate(args).model_dump(mode="json")
                except ValueError as exc:
                    error = {"stage":stage_index, "operation_id":step.operation_id,
                             "message":str(exc)[:500]}
                # Charge the complete validated input, including constants and
                # defaults. A small bound key must not hide a large ciphertext.
                # This is a serialized-input work proxy, not a CPU instruction count.
                amount = max(1,len(_json(inputs if inputs is not None else args)))
                if work + amount > max_work:
                    reason, paused = "work_limit", True; break
                work += amount
                try:
                    if error is not None:
                        raise ValueError(error["message"])
                    kernel_calls += 1
                    result = operation.kernel(**inputs)
                    try:
                        result = operation.result.model_validate(result).model_dump(mode="json")
                    except ValidationError as exc:
                        raise RuntimeError("operation violated its output contract") from exc
                    output = result[step.output_field]
                    if type(output) is not str:
                        raise ValueError("selected output is not text (decoding/padding may have failed)")
                    if len(output) > MAX_TEXT:
                        raise ValueError("intermediate output exceeds bounded text size")
                    info = {k:result[k] for k in ("trailing_digits", "dropped_offsets", "consumed_digits", "padding_valid") if k in result}
                    # Trace counts preserve selection losses without mistaking
                    # per-step bookkeeping for end-to-end dependency analysis.
                    if "dropped_offsets" in info:
                        info["dropped_count"] = len(info.pop("dropped_offsets"))
                except ValueError as exc:
                    error = {"stage":stage_index, "operation_id":step.operation_id,
                             "message":str(exc)[:500]}
                size = len(key[2]) + (len(output) if output is not None else 0)
                if len(cache)<512 and cache_chars+size<=4000000:
                    cache[key] = output, info, error; cache_chars += size
            trace.append({"stage":stage_index,"choice":choice,"operation_id":step.operation_id,
                          "input_length":len(text),"output_length":len(output) if output is not None else None,
                          **info})
            if error is not None:
                # Reused errors retain the *current* stage/recipe provenance.
                error = {**error, "stage":stage_index}
                break
            text = output
        if paused:
            break  # resume cursor points to the incomplete recipe, never past it
        matched = error is None and matches(text)
        trials.append({"ordinal":cursor,"choices":indexes,
                       "outcome":"INVALID_RECIPE_INPUT" if error else "CHECKPOINT_MATCH" if matched else "NO_CHECKPOINT_MATCH",
                       "error":error})
        if matched:
            hits.append({"ordinal":cursor,"choices":indexes,"text":text,"trace":trace,
                         "evidence_kind":"CHECKPOINT_MATCH_ONLY"})
        cursor += 1
        if len(hits) >= max_matches:
            reason = "match_limit"; break
    if cursor == total:
        reason = "exhausted"
    return {"matches":hits,"trials":trials,"recipe_count":total,"start":start,
            "next_start":cursor if cursor<total else None,
            "complete":cursor==total and start==0,"range_exhausted":cursor==total,
            "termination_reason":reason,"kernel_calls":kernel_calls,"cache_hits":cache_hits,
            "work_units":work,"checkpoint":p.checkpoint.model_dump(),
            "scope":"Enumerated only the supplied ordered recipe product. Checkpoint matches are not new puzzle solutions. "
                    "Errors do not reject the broader hypothesis; source labels are caller assertions. "
                    "Work units count canonical JSON characters of complete validated inputs on cache misses, including constants/defaults; "
                    "they are not CPU instructions. Shared computation is not independent reproduction. "
                    "Trace is not a source-dependency proof."}


def operations(make):
    return [make("mechanism.scan","Search a finite product of decoding recipes",
        "Preserve recipe paths, reuse identical intermediate work and test an explicit external checkpoint.",
        ScanSpec,scan,"recipe mechanism hypothesis pipeline decoding search shared prefix classical cipher",
        "Checkpoint matches in caller-declared recipes only; no automatic solution or completeness beyond stated range.",
        "6 stages,64 alternatives/stage,1M declared recipes,512 trials,16 matches; text/work/time/cache budgets.",
        cacheable=False,matches=list[dict],trials=list[dict],recipe_count=int,start=int,next_start=int|None,
        complete=bool,range_exhausted=bool,termination_reason=str,kernel_calls=int,cache_hits=int,
        work_units=int,checkpoint=dict,scope=str)]
