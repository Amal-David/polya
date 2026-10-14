"""Optional local experiment cache, kept outside stateless operations."""

import hashlib
import json
import sqlite3
import time
from .catalog import canonical_json, execute_prepared, make_receipt, prepare


class Session:
    def __init__(self, path):
        self.connection = sqlite3.connect(path)
        self.connection.execute("CREATE TABLE IF NOT EXISTS results (key TEXT PRIMARY KEY, inputs TEXT NOT NULL, envelope TEXT NOT NULL)")
        self.connection.execute("CREATE TABLE IF NOT EXISTS calls (id INTEGER PRIMARY KEY, key TEXT NOT NULL, at REAL NOT NULL, cache_hit INTEGER NOT NULL)")
        self.connection.commit()

    def run(self, operation_id: str, inputs: dict):
        op, validated, identity, key = prepare(operation_id, inputs)
        row = self.connection.execute("SELECT inputs,envelope FROM results WHERE key=?", (key,)).fetchone() if op.cacheable else None
        cache_hit = row is not None
        if cache_hit:
            try:
                stored_identity = json.loads(row[0])
                envelope = json.loads(row[1])
                result = envelope["result"]
                if op.result:
                    result = op.result.model_validate(result).model_dump(mode="json")
                expected = make_receipt(op, validated, identity, key, result)
                if (stored_identity != identity or envelope["receipt"] != expected
                        or envelope["operation_id"] != op.operation_id
                        or set(envelope) != {"operation_id", "result", "receipt"}):
                    raise ValueError("metadata mismatch")
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("cache corruption: input, result, or receipt mismatch") from exc
        else:
            envelope = execute_prepared(op, validated, identity, key)
            # Never reuse an execution spanning a runtime-mode transition as
            # though it ran wholly in either the initial or final mode.
            if op.cacheable and not envelope["receipt"]["runtime_observations"]["changed"]:
                self.connection.execute("INSERT INTO results VALUES (?,?,?)", (key, canonical_json(identity), canonical_json(envelope)))
        self.connection.execute("INSERT INTO calls (key,at,cache_hit) VALUES (?,?,?)", (key, time.time(), int(cache_hit)))
        self.connection.commit()
        return {**envelope, "cache_hit": cache_hit}

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

