#!/usr/bin/env python3
"""Positive and negative controls for the structural editorial prepublish gate."""
import copy
import unittest

from check_evidence import assess


def fixtures():
    item = {
        "title": "平台發布測試功能",
        "title_en": "Platform launches a pilot feature",
        "summary": "該功能仍然處於限制測試階段。",
        "summary_en": "The feature remains in a limited pilot.",
        "source": "Official Blog",
        "url": "https://example.org/news/pilot",
        "time": "10月26日",
        "section": "廣告平台 & 行銷科技",
        "why": "可檢視合規或測量影響。",
        "why_en": "Check privacy and measurement implications.",
    }
    data = {"date": "2026-10-26", "sections": ["廣告平台 & 行銷科技"], "items": [item]}
    src = "https://example.org/news/pilot"
    evidence = {
        "schema_version": "1.0", "edition_date_hkt": "2026-10-26",
        "verified_at_hkt": "2026-10-26T12:00:00+08:00", "status": "reviewed",
        "stories": [{
            "story_id": "2026-10-26-pilot",
            "published_article_url": src,
            "event_date": "2026-10-25",
            "first_published_date": "2026-10-26",
            "source_documents": [{
                "url": src, "source_class": "A",
                "access_state": "accessible",
                "accessed_at_hkt": "2026-10-26T11:30:00+08:00"
            }],
            "material_claims": [{
                "claim_zh": "官方宣稱功能正在受限測試。",
                "support_url": src,
                "evidence_locator": "官方更新頁面第一段",
                "status": "attributed", "second_pass_checked": True
            }],
            "editorial_relevance_score": {
                "direct_marketing_relevance": 26, "business_impact": 20,
                "actionability": 18, "market_relevance": 13, "novelty": 9
            },
            "impact": "Medium", "recommended_response": "Monitor",
            "editorial_decision": "approved", "needs_human_review": False
        }]
    }
    return data, evidence


class GateControls(unittest.TestCase):
    def test_valid_packet_passes(self):
        data, evidence = fixtures()
        self.assertEqual(assess(data, evidence), [])

    def test_unapproved_publish_alias_fails(self):
        data, evidence = fixtures()
        evidence["stories"][0]["editorial_decision"] = "publish"
        self.assertTrue(assess(data, evidence))

    def test_no_evidence_fails(self):
        data, evidence = fixtures()
        evidence["stories"] = []
        self.assertTrue(assess(data, evidence))

    def test_missing_translation_fails(self):
        data, evidence = fixtures()
        del data["items"][0]["title_en"]
        self.assertTrue(assess(data, evidence))

    def test_unchecked_claim_fails(self):
        data, evidence = fixtures()
        evidence["stories"][0]["material_claims"][0]["second_pass_checked"] = False
        self.assertTrue(assess(data, evidence))

    def test_unverified_claim_fails(self):
        data, evidence = fixtures()
        evidence["stories"][0]["material_claims"][0]["status"] = "uncertain"
        self.assertTrue(assess(data, evidence))

    def test_human_review_hold_fails(self):
        data, evidence = fixtures()
        evidence["stories"][0]["needs_human_review"] = True
        self.assertTrue(assess(data, evidence))

    def test_mismatched_evidence_url_fails(self):
        data, evidence = fixtures()
        evidence["stories"][0]["published_article_url"] = "https://example.org/other-story"
        self.assertTrue(assess(data, evidence))

    def test_duplicate_published_url_fails(self):
        data, evidence = fixtures()
        data["items"].append(copy.deepcopy(data["items"][0]))
        self.assertTrue(assess(data, evidence))

    def test_missing_source_document_fails(self):
        data, evidence = fixtures()
        evidence["stories"][0]["source_documents"] = []
        self.assertTrue(assess(data, evidence))

    def test_future_event_fails(self):
        data, evidence = fixtures()
        evidence["stories"][0]["event_date"] = "2026-11-01"
        self.assertTrue(assess(data, evidence))


if __name__ == "__main__":
    unittest.main()
