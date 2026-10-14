"""Polya: deterministic puzzle operations; the caller owns strategy."""

__version__ = "0.3.0"


def find(query: str = "", *, operation_id: str | None = None, limit: int = 5):
    from .catalog import find as _find
    return _find(query, operation_id=operation_id, limit=limit)


def list_operations():
    from .catalog import list_operations as _list_operations
    return _list_operations()


def run(operation_id: str, inputs: dict):
    from .catalog import run as _run
    return _run(operation_id, inputs)

