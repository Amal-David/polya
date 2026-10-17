"""Typed, bounded educational example library; never executes retrieved content."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import json
from pathlib import Path
import re
from urllib.parse import urlparse
from ..jsonio import loads

MAX_BYTES = 2_000_000

def read_bytes(path: str | Path) -> bytes:
    """Read at most 2 MB, including under concurrent file growth."""
    with Path(path).open('rb') as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('input exceeds byte limit')
    return raw

def read_text(path: str | Path) -> str:
    return read_bytes(path).decode('utf-8')

def read_json(path: str | Path) -> object:
    """Bounded strict JSON: reject duplicate keys and non-finite constants."""
    from .reset import canonical
    value = loads(read_text(path))
    # parse_constant alone does not catch finite-looking exponents such as 1e400.
    canonical(value)
    return value

def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 30000:
        raise ValueError('expected nonempty string <= 30000 characters')
    return value

def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not 1 <= len(value) <= 32:
        raise ValueError('expected 1..32 strings')
    return tuple(_text(x) for x in value)

def _keys(value: object, keys: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f'expected exact fields: {sorted(keys)}')
    return value

@dataclass(frozen=True)
class Source:
    url: str
    author: str
    title: str
    license_basis: str

@dataclass(frozen=True)
class ToyAdaptation:
    provenance: str
    problem: str
    solution: str
    verification: str

@dataclass(frozen=True)
class Example:
    id: str
    methods: tuple[str, ...]
    source: Source
    documented_evidence: str
    reconstruction: str
    toy_adaptation: ToyAdaptation
    applicability: tuple[str, ...]
    limits: tuple[str, ...]
    falsifiable_test: str

    @classmethod
    def parse(cls, value: object) -> 'Example':
        d = _keys(value, set(cls.__dataclass_fields__))
        source = _keys(d['source'], set(Source.__dataclass_fields__))
        toy = _keys(d['toy_adaptation'], set(ToyAdaptation.__dataclass_fields__))
        source = Source(**{k: _text(v) for k, v in source.items()})
        if urlparse(source.url).scheme != 'https' or not urlparse(source.url).netloc:
            raise ValueError('source must have an HTTPS URL')
        identifier = _text(d['id'])
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', identifier):
            raise ValueError('invalid example id')
        return cls(identifier, _strings(d['methods']), source,
                   _text(d['documented_evidence']), _text(d['reconstruction']),
                   ToyAdaptation(**{k: _text(v) for k, v in toy.items()}),
                   _strings(d['applicability']), _strings(d['limits']),
                   _text(d['falsifiable_test']))

    def to_dict(self) -> dict:
        return json.loads(json.dumps(asdict(self)))


def load_library(path: str | Path) -> tuple[Example, ...]:
    data = read_json(path)
    if not isinstance(data, list) or not 1 <= len(data) <= 256:
        raise ValueError('expected 1..256 examples')
    examples = tuple(Example.parse(x) for x in data)
    if len({x.id for x in examples}) != len(examples):
        raise ValueError('duplicate example id')
    return examples


def retrieve(examples: tuple[Example, ...], query: str, *, limit: int = 3) -> list[dict]:
    """Transparent lexical ranking on method/applicability only; not a learned ranker."""
    if type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError('limit must be 1..10')
    if (not isinstance(examples, tuple) or len(examples) > 256 or
            any(not isinstance(ex, Example) for ex in examples)):
        raise ValueError('expected at most 256 parsed examples')
    _text(query)
    terms = set(re.findall(r'[a-z0-9]+', query.lower()))
    ranked = []
    for ex in examples:
        searchable = ' '.join(ex.methods + ex.applicability)
        matched = terms & set(re.findall(r'[a-z0-9]+', searchable.lower()))
        if matched:
            ranked.append((len(matched), ex.id, sorted(matched), ex))
    ranked.sort(key=lambda row: (-row[0], row[1]))
    return [{'example': ex.to_dict(), 'matched_terms': matched, 'score': score,
             'scope': 'lexical method match, not probability or solution evidence'}
            for score, _, matched, ex in ranked[:limit]]


# Freeze the installed development library once; it is not a live corpus or holdout.
_BUILTIN = load_library(Path(__file__).parent / 'data' / 'examples.json')


def builtin_library() -> tuple[Example, ...]:
    """Immutable parsed examples. Returned retrieval dictionaries are detached."""
    return _BUILTIN
