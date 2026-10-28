"""Publication boundaries: incomplete news cannot publish; current news is reused."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from edition_packet import current_packet, prepare, read_json, resolve_edition, validate, write_json
from release_state import asset_paths, make_receipt, observe, plan, receipt_errors, sha, StoryCounter

ROOT = Path(__file__).resolve().parents[1]


class PublicationControls(unittest.TestCase):
    def setUp(self):
        # The already reviewed issue is a real compatibility fixture; mutations
        # stay in memory/temp directories and never alter its approved evidence.
        self.packet = read_json(ROOT / "editorial/editions/2026-10-28.json")
        self.date = self.packet["data"]["date"]
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        # Synthetic built/live bytes isolate these controls from whichever day's
        # real packet CI has just materialized, before that day's build exists.
        for path in asset_paths(self.date):
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"fixture asset")
            if path.endswith(".html"):
                target.write_text('<html>' + '<article class="story"></article>' * len(self.packet["data"]["items"]) + '</html>')
        write_json(self.root / "data.json", self.packet["data"])
        write_json(self.root / f"editorial/evidence/{self.date}.json", self.packet["evidence"])
        write_json(self.root / f"editorial/localization_review/{self.date}.json", self.packet["localization_review"])
        data_hash = sha((self.root / "data.json").read_bytes())
        proof_hash = sha((self.root / f"editorial/evidence/{self.date}.json").read_bytes())
        write_json(self.root / "edm/payload.json", {"edition_date": self.date,
                   "headline_count": len(self.packet["data"]["items"]), "verification_status": "editorial_approved",
                   "data_sha256": data_hash, "evidence_sha256": proof_hash,
                   "edition_id": "ai-marketing-daily-en-" + self.date})
        write_json(self.root / f"editorial/releases/{self.date}.json", {"status": "PUBLISHED & VERIFIED",
                   "edition_date_hkt": self.date, "published_story_count": len(self.packet["data"]["items"]),
                   "data_sha256": data_hash, "deployed_evidence_sha256": proof_hash})

    def test_current_reviewed_issue_is_a_valid_packet(self):
        self.assertEqual(validate(self.packet, self.date), [])

    def test_draft_is_not_approval(self):
        self.packet["status"] = "draft"
        self.assertTrue(validate(self.packet, self.date))

    def test_nine_stories_do_not_meet_the_floor(self):
        for obj, key in [(self.packet["data"], "items"), (self.packet["evidence"], "stories"),
                         (self.packet["localization_review"], "items")]:
            obj[key] = obj[key][:9]
        self.assertTrue(validate(self.packet, self.date))

    def test_missing_independent_source_review_blocks_publication(self):
        self.packet["evidence"]["stories"][0]["independent_review"] = None
        self.assertTrue(validate(self.packet, self.date))

    def test_conditional_approval_is_not_final_approval(self):
        self.packet["evidence"]["stories"][0]["editorial_decision"] = "approved_conditional"
        self.assertTrue(validate(self.packet, self.date))

    def test_human_review_hold_stays_a_hold(self):
        self.packet["evidence"]["stories"][0]["needs_human_review"] = True
        self.assertTrue(validate(self.packet, self.date))

    def test_scoring_alone_cannot_replace_claims(self):
        self.packet["evidence"]["stories"][0]["claims"] = []
        self.assertTrue(validate(self.packet, self.date))

    def test_sixty_point_selection_floor(self):
        self.packet["evidence"]["stories"][0]["editorial_relevance_score"]["total"] = 59
        self.assertTrue(validate(self.packet, self.date))

    def test_changed_title_must_update_evidence_and_localization(self):
        self.packet["data"]["items"][0]["title"] = "Changed title without matching review"
        self.assertTrue(validate(self.packet, self.date))

    def test_old_issue_cannot_be_renamed_to_today(self):
        self.assertTrue(validate(self.packet, "2099-01-01"))

    def test_invalid_badge_and_region_do_not_reach_renderer(self):
        self.packet["data"]["items"][0].update(action="Long recommendation", region="Global")
        self.assertTrue(validate(self.packet, self.date))

    def test_invalid_input_does_not_partly_materialize_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.packet["status"] = "draft"
            write_json(root / f"editorial/editions/{self.date}.json", self.packet)
            with self.assertRaises(ValueError):
                prepare(root, self.date)
            self.assertFalse((root / "data.json").exists())

    def test_valid_packet_materializes_all_three_inputs_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / f"editorial/editions/{self.date}.json", self.packet)
            prepare(root, self.date)
            self.assertEqual(current_packet(root), self.packet)

    def test_docs_do_not_force_yesterdays_issue_to_be_today(self):
        self.assertEqual(resolve_edition({"date": "2026-10-27"}, "2026-10-28", ["editorial/DAILY_SOP_v1.0.md"]), ("2026-10-27", False))

    def test_a_new_packet_requires_the_actual_hong_kong_date(self):
        self.assertEqual(resolve_edition({"date": "2026-10-27"}, "2026-10-28", ["editorial/editions/2026-10-28.json"]), ("2026-10-28", True))
        with self.assertRaises(ValueError):
            resolve_edition({"date": "2026-10-27"}, "2026-10-28", ["editorial/editions/2026-10-27.json"])

    def test_direct_derived_edits_cannot_be_silently_replaced_by_a_packet(self):
        with self.assertRaisesRegex(ValueError, "canonical edition packet"):
            resolve_edition({"date": "2026-10-28"}, "2026-10-28", ["data.json"], canonical_exists=True)

    def test_count_real_articles_not_css_class_mentions(self):
        counter = StoryCounter()
        counter.feed('<style>.story{color:red}</style><article class="story lead"></article><div class="story"></div>')
        self.assertEqual(counter.count, 1)

    def test_shared_receipt_does_not_depend_on_a_stale_task_chat(self):
        data = self.packet["data"]
        proof = (json.dumps(self.packet["evidence"], ensure_ascii=False, indent=2) + "\n").encode()
        receipt = {"status": "PUBLISHED & VERIFIED", "edition_date_hkt": self.date,
                   "published_story_count": len(data["items"]),
                   "data_sha256": sha((json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()),
                   "deployed_evidence_sha256": sha(proof)}
        self.assertEqual(receipt_errors(receipt, data, proof, "success"), [])
        self.assertTrue(receipt_errors(receipt, data, proof, "failure"))
        receipt["status"] = "HELD"
        self.assertTrue(receipt_errors(receipt, data, proof, "success"))

    def test_mismatching_receipt_bytes_are_rejected(self):
        record = {"status": "PUBLISHED & VERIFIED", "edition_date_hkt": self.date,
                  "published_story_count": len(self.packet["data"]["items"]),
                  "data_sha256": "0" * 64, "deployed_evidence_sha256": "0" * 64}
        self.assertTrue(receipt_errors(record, self.packet["data"], b"changed evidence"))

    def test_a_failed_live_asset_cannot_create_a_success_receipt(self):
        release_plan = {"edition_date_hkt": self.date, "expected_asset_sha256": {"index.html": "0" * 64},
                        "deployment_required": True, "action": "DEPLOY_VERIFIED_CANDIDATE"}
        with self.assertRaisesRegex(ValueError, "live acceptance failed"):
            make_receipt(self.root, release_plan, {"index.html": {"error": "404"}}, "a" * 40, "b" * 40,
                         "https://github.com/carriehw/ai-marketing-daily/actions/runs/1")

    def reviewed_observations(self):
        p = plan(self.root, self.date, fetcher=lambda path: (self.root / path).read_bytes())
        return p, observe(p["expected_asset_sha256"], lambda path: (self.root / path).read_bytes())

    def test_matching_approved_site_creates_a_receipt_without_any_send(self):
        p, observed = self.reviewed_observations()
        evidence = self.root / f"editorial/evidence/{self.date}.json"
        before = evidence.read_bytes()
        receipt = make_receipt(self.root, p, observed, "a" * 40, "b" * 40,
                               "https://github.com/carriehw/ai-marketing-daily/actions/runs/1")
        self.assertEqual(receipt["status"], "PUBLISHED & VERIFIED")
        self.assertEqual(set(receipt["language_article_counts"].values()), {len(self.packet["data"]["items"])})
        self.assertFalse(receipt["newsletter_sent_by_this_run"])
        self.assertFalse(receipt["social_posted_by_this_run"])
        self.assertEqual(evidence.read_bytes(), before)

    def test_live_language_count_mismatch_cannot_create_a_receipt(self):
        p, observed = self.reviewed_observations()
        observed["en/index.html"]["article_count"] = 9
        with self.assertRaisesRegex(ValueError, "article count"):
            make_receipt(self.root, p, observed, "a" * 40, "b" * 40,
                         "https://github.com/carriehw/ai-marketing-daily/actions/runs/1")

    def test_live_newsletter_with_different_evidence_cannot_create_a_receipt(self):
        p, observed = self.reviewed_observations()
        observed["edm/payload.json"]["payload"]["evidence_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "newsletter"):
            make_receipt(self.root, p, observed, "a" * 40, "b" * 40,
                         "https://github.com/carriehw/ai-marketing-daily/actions/runs/1")

    def test_current_live_build_is_audited_without_redeploying(self):
        p = plan(self.root, self.date, fetcher=lambda path: (self.root / path).read_bytes())
        self.assertFalse(p["deployment_required"])
        self.assertEqual(p["action"], "AUDIT_ALREADY_CURRENT")

    def test_changed_live_asset_requires_publication_not_false_success(self):
        p = plan(self.root, self.date, fetcher=lambda path: b"wrong" if path == "index.html" else (self.root / path).read_bytes())
        self.assertTrue(p["deployment_required"])

    def test_first_approved_issue_without_receipt_can_reach_deployment(self):
        (self.root / f"editorial/releases/{self.date}.json").unlink()
        def forbidden(_):
            self.fail("a first approved issue does not need an existing live receipt")
        p = plan(self.root, self.date, fetcher=forbidden)
        self.assertTrue(p["deployment_required"])

    def test_pull_request_does_not_fetch_live_or_deploy(self):
        def forbidden(_):
            self.fail("PR should not access production for its candidate check")
        p = plan(self.root, self.date, candidate_only=True, fetcher=forbidden)
        self.assertFalse(p["deployment_required"])
        self.assertEqual(p["action"], "CANDIDATE_CHECKED")


if __name__ == "__main__":
    unittest.main()
