"""Synthetic date-gate fixtures; never a publishable news edition."""
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from verify_dates import run, reviewed_scheduled_dates


class ScheduledDateControls(unittest.TestCase):
    def setUp(self):
        self.url = "https://example.com/synthetic-plan"
        self.claim = {"claim_zh": "產品接入計劃於11月2日推出。", "status": "attributed",
                      "second_pass_checked": True, "support_url": self.url,
                      "evidence_locator": "Synthetic original announcement schedule"}
        self.story = {"source_story_url": self.url, "editorial_decision": "approved",
                      "needs_human_review": False, "material_claims": [self.claim],
                      "scheduled_dates": [{"date": "2026-11-02", "status": "announced_plan", "claim_zh": self.claim["claim_zh"]}],
                      "source_documents": [{"url": self.url, "source_class": "A", "access_state": "accessible"}]}
        self.data = {"items": [{"time": "10月29日", "url": self.url,
                                "detail": "產品接入計劃為11月2日。"}]}

    def failures(self):
        return run(self.data, (10, 31), scheduled_dates=reviewed_scheduled_dates({"stories": [self.story]}))[0]

    def test_checked_announcement_retains_future_rollout_date(self):
        self.assertEqual(self.failures(), [])

    def test_scheduled_effective_date_is_allowed(self):
        self.data["items"][0]["detail"] = "官方預告設定由11月2日起生效。"
        self.assertEqual(self.failures(), [])

    def test_future_wording_without_recorded_claim_fails(self):
        self.story["scheduled_dates"] = []
        self.assertTrue(self.failures())

    def test_unchecked_claim_fails(self):
        self.claim["second_pass_checked"] = False
        self.assertTrue(self.failures())

    def test_inaccessible_original_fails(self):
        self.story["source_documents"][0]["access_state"] = "blocked"
        self.assertTrue(self.failures())

    def test_human_hold_fails(self):
        self.story["needs_human_review"] = True
        self.assertTrue(self.failures())

    def test_wrong_date_fails(self):
        self.story["scheduled_dates"][0]["date"] = "2026-11-03"
        self.assertTrue(self.failures())

    def test_plan_cannot_claim_future_event_completed(self):
        self.data["items"][0]["detail"] = "產品已於11月2日完成推出。"
        self.assertTrue(self.failures())

    def test_completed_event_cannot_borrow_plan_word(self):
        self.data["items"][0]["detail"] = "計劃已於11月2日完成。"
        self.assertTrue(self.failures())

    def test_unrelated_future_date_stays_blocked(self):
        self.data["items"][0]["detail"] += "另外計劃11月3日推出。"
        self.assertTrue(self.failures())


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

