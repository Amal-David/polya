"""Polya: deterministic puzzle operations; the caller owns strategy."""

__version__ = "0.2.2"


def find(query: str = "", *, operation_id: str | None = None, limit: int = 5):
    from .catalog import find as _find
    return _find(query, operation_id=operation_id, limit=limit)


def list_operations():
    from .catalog import OPS, find as _find
    return _find(limit=len(OPS))


def run(operation_id: str, inputs: dict):
    from .catalog import run as _run
    return _run(operation_id, inputs)

