from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "expense_totals.py"


class ExpenseTotalsCliTests(unittest.TestCase):
    def run_cli(
        self, csv_text: str, *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "expenses.csv"
            input_path.write_text(csv_text, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(SCRIPT), str(input_path), *arguments],
                text=True,
                capture_output=True,
                check=False,
            )

    def test_totals_are_exact_sorted_json_and_allow_refunds(self) -> None:
        data = "category,amount\nTravel,10.20\nFood,4.50\nTravel,-2.20\nFood,1\n"
        first = self.run_cli(data)
        second = self.run_cli(data)
        expected = '{\n  "Food": "5.50",\n  "Travel": "8.00"\n}\n'
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, expected)
        self.assertEqual(second.stdout, first.stdout)
        self.assertEqual(first.stderr, "")

    def test_header_order_may_differ(self) -> None:
        result = self.run_cli("amount,category\n12.34,Books\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"Books": "12.34"})

    def test_large_amounts_sum_without_decimal_context_rounding(self) -> None:
        result = self.run_cli(
            "category,amount\nLarge,1234567890123456789012345.67\nLarge,0.01\n"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"Large": "1234567890123456789012345.68"})

    def test_header_only_file_yields_empty_object(self) -> None:
        result = self.run_cli("category,amount\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "{}\n")

    def test_unequal_scales_preserve_cents_after_large_whole_amounts(self) -> None:
        whole = "1" + "0" * 100
        result = self.run_cli(f"category,amount\nLarge,{whole}\nLarge,0.01\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"Large": whole + ".01"})

    def test_category_filter_returns_only_selected_total(self) -> None:
        result = self.run_cli(
            "category,amount\nFood,4.50\nTravel,10.00\nFood,1.25\n",
            "--category",
            "Food",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '{\n  "Food": "5.75"\n}\n')
        self.assertEqual(result.stderr, "")

    def test_absent_category_filter_returns_empty_object(self) -> None:
        result = self.run_cli("category,amount\nFood,4.50\n", "--category", "Travel")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "{}\n")
        self.assertEqual(result.stderr, "")

    def test_filter_still_rejects_invalid_unselected_rows(self) -> None:
        result = self.run_cli(
            "category,amount\nFood,4.50\nTravel,not-an-amount\n",
            "--category",
            "Food",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("line 3: invalid amount", result.stderr)

    def test_malformed_inputs_fail_without_partial_stdout(self) -> None:
        invalid_inputs = {
            "wrong header": "category,amount,extra\nFood,1,ignored\n",
            "missing field": "category,amount\nFood\n",
            "extra field": "category,amount\nFood,1,extra\n",
            "empty category": "category,amount\n ,1\n",
            "nonnumeric": "category,amount\nFood,abc\n",
            "too precise": "category,amount\nFood,1.001\n",
            "nan": "category,amount\nFood,NaN\n",
            "infinity": "category,amount\nFood,Infinity\n",
            "empty file": "",
        }
        for label, csv_text in invalid_inputs.items():
            with self.subTest(label=label):
                result = self.run_cli(csv_text)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn("expense_totals: error:", result.stderr)


if __name__ == "__main__":
    unittest.main()
