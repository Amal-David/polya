import json
import tempfile
import unittest
from unittest import mock

from puzzleops.session import Session


class SessionTests(unittest.TestCase):
    def test_resume_and_preserve_distinct_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            db = folder + "/case.sqlite"
            with Session(db) as session:
                first = session.run("text.profile", {"text": "Ab "})
                self.assertFalse(first["cache_hit"])
            with Session(db) as session:
                again = session.run("text.profile", {"text": "Ab "})
                changed = session.run("text.profile", {"text": "ab "})
                self.assertTrue(again["cache_hit"])
                self.assertFalse(changed["cache_hit"])
                self.assertEqual(first["receipt"], again["receipt"])
                self.assertFalse(again["receipt"]["independently_reproduced"])

    def test_runtime_change_invalidates_cache(self):
        with Session(":memory:") as session:
            first = session.run("text.profile", {"text": "abc"})
            with mock.patch("puzzleops.catalog.implementation_fingerprint", return_value="different-code-and-runtime"):
                second = session.run("text.profile", {"text": "abc"})
            self.assertFalse(second["cache_hit"])
            self.assertNotEqual(first["receipt"]["experiment_key"], second["receipt"]["experiment_key"])

    def test_partial_result_remains_partial_on_cache_hit(self):
        with Session(":memory:") as session:
            args = {"slots": [["a", "b"]], "limit": 1}
            session.run("candidate.expand", args)
            result = session.run("candidate.expand", args)
            self.assertTrue(result["cache_hit"])
            self.assertEqual(result["result"]["status"], "PARTIAL")
            self.assertFalse(result["result"]["complete"])

    def test_forged_receipt_is_rejected(self):
        with Session(":memory:") as session:
            result = session.run("text.profile", {"text": "abc"})
            key = result["receipt"]["experiment_key"]
            row = session.connection.execute("SELECT envelope FROM results WHERE key=?", (key,)).fetchone()
            value = json.loads(row[0]); value["receipt"]["independently_reproduced"] = True
            session.connection.execute("UPDATE results SET envelope=? WHERE key=?", (json.dumps(value), key))
            with self.assertRaisesRegex(ValueError, "cache corruption"):
                session.run("text.profile", {"text": "abc"})


if __name__ == "__main__":
    unittest.main()

