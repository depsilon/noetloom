from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ExampleTests(unittest.TestCase):
    def run_command(self, relative, command):
        result = subprocess.run(command, cwd=ROOT / "examples" / relative, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_expense_cli_behavior(self):
        self.run_command("expense-totals", [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"])

    def test_readable_tool_shelf_behavior(self):
        self.run_command("tool-shelf", [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"])

    def test_reading_list_state_behavior(self):
        self.assertIsNotNone(shutil.which("node"), "Node 22+ is required to validate the maintained website example")
        self.run_command("reading-list", ["node", "--test", "tests/core.test.cjs"])

    def test_reading_list_browser_observation_is_bound_to_current_sources(self):
        self.run_command("reading-list", [sys.executable, "-B", "tests/check_browser_evidence.py"])


if __name__ == "__main__":
    unittest.main()
