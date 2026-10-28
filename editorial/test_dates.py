"""Synthetic date-gate fixtures; never a publishable news edition."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from verify_dates import run


class SameDayDateControls(unittest.TestCase):
    def setUp(self):
        self.url = "https://example.com/synthetic-date-fixture"
        self.data = {"items": [{"time": "10月29日", "url": self.url,
                                "title": "日期測試資料"}]}

    def test_reviewed_same_day_source_is_allowed(self):
        failures, _ = run(self.data, (10, 29), same_day_verified_urls={self.url})
        self.assertEqual(failures, [])

    def test_unreviewed_same_day_date_is_a_normal_hold(self):
        failures, _ = run(self.data, (10, 29))
        self.assertTrue(any("ALLOW_TODAY" in failure for failure in failures))

    def test_allowed_same_day_still_rejects_future_claim(self):
        self.data["items"][0]["detail"] = "10月30日完成。"
        failures, _ = run(self.data, (10, 29), same_day_verified_urls={self.url})
        self.assertTrue(any("晚於" in failure for failure in failures))

    def run_cli(self, publication_date="2026-10-29", human_hold=False):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "data.json").write_text(json.dumps(self.data), encoding="utf-8")
            proof = {"stories": [{"source_story_url": self.url,
                "source_date_display": "10月29日", "editorial_decision": "approved",
                "needs_human_review": human_hold,
                "source_documents": [{"source_publication_date": publication_date,
                    "source_class": "A", "evidence_locator": "Synthetic source date section"}]}]}
            path = root / "editorial/evidence/2026-10-29.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(proof), encoding="utf-8")
            return subprocess.run([sys.executable, str(ROOT / "verify_dates.py"),
                                   "--today", "2026-10-29"], cwd=root,
                                  capture_output=True, text=True)

    def test_new_day_cli_reads_reviewed_same_day_evidence(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_old_publication_date_cannot_approve_same_day_label(self):
        result = self.run_cli(publication_date="2026-10-28")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_human_hold_does_not_approve_same_day_label(self):
        result = self.run_cli(human_hold=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
