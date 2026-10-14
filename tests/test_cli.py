import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliTests(unittest.TestCase):
    def test_stdin_and_structured_error(self):
        result = subprocess.run([sys.executable, "-m", "polya", "run", "bytes.decode", "--input", "-"],
                                input='{"encoding":"hex","value":"616263"}', text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["result"]["hex"], "616263")
        result = subprocess.run([sys.executable, "-m", "polya", "run", "bytes.decode", "--input", "-"],
                                input='{"encoding":"hex","value":"odd"}', text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)["execution_status"], "ERROR")

    def test_corrupt_cache_is_structured_error(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "bad.sqlite"; db.write_text("not a database")
            result = subprocess.run([sys.executable, "-m", "polya", "run", "text.profile", "--input", "-", "--db", str(db)],
                                    input='{"text":"abc"}', text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stderr)["execution_status"], "ERROR")


if __name__ == "__main__":
    unittest.main()
