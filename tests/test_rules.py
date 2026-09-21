"""
Unit tests for the inference engine.

Run from the project root:
    python -m pytest tests/ -v
    (or simply: python tests/test_rules.py)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import knowledge_base as kb  # noqa: E402
from rules_engine import RULES, Analysis, classify, evaluate, normalise_score  # noqa: E402


class TestPreprocessing(unittest.TestCase):

    def test_whitespace_and_case_normalised(self):
        a = Analysis.build("  BREAKING   News   Here  ", "BBC")
        self.assertEqual(a.text, "breaking news here")
        self.assertEqual(a.source, "bbc")

    def test_word_count(self):
        a = Analysis.build("one two three four", "")
        self.assertEqual(a.word_count, 4)

    def test_short_acronyms_are_not_shouting(self):
        # US and UK are legitimate; SHOCKING is not.
        a = Analysis.build("The US and UK agreed on terms", "")
        self.assertEqual(a.caps_words, [])

    def test_urls_extracted(self):
        a = Analysis.build("See https://example.com/story for more", "")
        self.assertEqual(len(a.urls), 1)


class TestIndividualRules(unittest.TestCase):

    def _fired_ids(self, text, source=""):
        return {f["rule_id"] for f in evaluate(text, source)["findings"]}

    def test_unknown_source_flagged(self):
        self.assertIn("R01", self._fired_ids("Something happened today.", ""))

    def test_trusted_source_is_mitigating(self):
        result = evaluate("A report was published today.", "Reuters")
        r01 = [f for f in result["findings"] if f["rule_id"] == "R01"][0]
        self.assertLess(r01["points"], 0)

    def test_unreliable_source_scores_highest(self):
        result = evaluate("A report was published.", "YourNewsWire")
        r01 = [f for f in result["findings"] if f["rule_id"] == "R01"][0]
        self.assertEqual(r01["points"], 18)

    def test_sensational_language(self):
        self.assertIn("R03", self._fired_ids("This shocking bombshell was exposed."))

    def test_clickbait(self):
        self.assertIn("R04", self._fired_ids("You won't believe what happened next."))

    def test_shouting_detected(self):
        self.assertIn("R05", self._fired_ids("THIS IS COMPLETELY URGENT NEWS everyone"))

    def test_normal_capitalisation_not_flagged(self):
        self.assertNotIn("R05", self._fired_ids(
            "The minister said the policy would take effect in April.", "BBC"))

    def test_excessive_punctuation(self):
        self.assertIn("R06", self._fired_ids("Can you believe it?!?! Amazing!!"))

    def test_unverified_claims(self):
        self.assertIn("R07", self._fired_ids("Sources say the deal is done."))

    def test_missing_evidence(self):
        self.assertIn("R08", self._fired_ids("The policy changed yesterday."))

    def test_strong_evidence_is_mitigating(self):
        result = evaluate(
            "According to a study published in Nature, data shows a 10 percent rise.",
            "Reuters")
        r08 = [f for f in result["findings"] if f["rule_id"] == "R08"][0]
        self.assertLess(r08["points"], 0)

    def test_promotional_percentage_is_not_evidence(self):
        # Regression: "100% guaranteed" once counted as statistical
        # evidence and wrongly suppressed the missing-evidence rule.
        self.assertIn("R08", self._fired_ids("This cure is 100% guaranteed."))

    def test_reported_statistic_counts_as_evidence(self):
        result = evaluate("Cases fell by 20 percent across the district "
                          "according to the survey data shows.", "BBC")
        r08 = [f for f in result["findings"] if f["rule_id"] == "R08"]
        self.assertTrue(not r08 or r08[0]["points"] < 0)

    def test_suspicious_link_is_not_treated_as_evidence(self):
        # Regression: a scam domain matched the "www." evidence marker,
        # so R02 flagged the link while R08 credited it as a citation.
        ids = self._fired_ids("Read the full story at www.health-truth-247.xyz now.")
        self.assertIn("R02", ids)
        self.assertIn("R08", ids)

    def test_do_your_own_research_is_not_evidence(self):
        # Regression: "do your own research" contains the evidence marker
        # "research", so conspiratorial framing suppressed R08.
        ids = self._fired_ids("Wake up and do your own research on this.")
        self.assertIn("R11", ids)
        self.assertIn("R08", ids)

    def test_genuine_research_reference_still_counts(self):
        a = Analysis.build("Researchers published the survey data shows a rise.", "")
        self.assertTrue(
            a.matches_outside(kb.EVIDENCE_MARKERS, kb.CONSPIRACY_PHRASES))

    def test_legitimate_link_still_counts_as_evidence(self):
        a = Analysis.build("Details at https://www.bbc.co.uk/news/article", "")
        self.assertIn("https://", a.matches(kb.EVIDENCE_MARKERS))

    def test_urgency_pressure(self):
        self.assertIn("R10", self._fired_ids("Share this before it's deleted!"))

    def test_conspiracy_framing(self):
        self.assertIn("R11", self._fired_ids("The mainstream media won't tell you this."))

    def test_absolute_claims(self):
        self.assertIn("R12", self._fired_ids("This remedy is 100% guaranteed."))


class TestWordBoundaryMatching(unittest.TestCase):
    """
    Regression: matching was substring-based, so "secret" fired inside
    "Secretary" and flagged ordinary government reporting as sensational.
    """

    def _fired_ids(self, text, source=""):
        return {f["rule_id"] for f in evaluate(text, source)["findings"]}

    def test_secret_does_not_match_secretary(self):
        self.assertNotIn("R03", self._fired_ids(
            "Transport Secretary Rajesh Kumar said the timetable changed.", "BBC"))

    def test_secret_still_matches_as_a_word(self):
        self.assertIn("R03", self._fired_ids("A secret deal was exposed."))

    def test_plural_forms_still_match(self):
        a = Analysis.build("The surveys and studies were noted.", "")
        self.assertIn("survey", a.matches({"survey"}))

    def test_https_urls_count_as_evidence_marker(self):
        a = Analysis.build("Details at https://example.com/report", "")
        self.assertIn("https://", a.matches(kb.EVIDENCE_MARKERS))


class TestScoring(unittest.TestCase):

    def test_negative_raw_score_clamps_to_zero(self):
        self.assertEqual(normalise_score(-20), 0)

    def test_risk_is_capped_at_100(self):
        self.assertEqual(normalise_score(500), 100)

    def test_classification_boundaries(self):
        self.assertEqual(classify(0), "REAL")
        self.assertEqual(classify(kb.THRESHOLD_SUSPICIOUS - 1), "REAL")
        self.assertEqual(classify(kb.THRESHOLD_SUSPICIOUS), "SUSPICIOUS")
        self.assertEqual(classify(kb.THRESHOLD_FAKE - 1), "SUSPICIOUS")
        self.assertEqual(classify(kb.THRESHOLD_FAKE), "FAKE")
        self.assertEqual(classify(100), "FAKE")


class TestEndToEnd(unittest.TestCase):

    FABRICATED = ("SHOCKING!! Sources say a MIRACLE cure was banned by BIG PHARMA!! "
                  "The mainstream media won't tell you. 100% guaranteed results. "
                  "Share this before it's deleted!!")

    CREDIBLE = ("According to a study published in Nature, researchers recorded a "
                "20 percent decrease in cases. Health Minister Anita Rao said the "
                "data shows steady improvement, confirmed by an official statement "
                "released on Tuesday.")

    def test_fabricated_article_classified_fake(self):
        result = evaluate(self.FABRICATED, "Unknown")
        self.assertEqual(result["verdict"], "FAKE")
        self.assertGreaterEqual(result["risk"], kb.THRESHOLD_FAKE)

    def test_credible_article_classified_real(self):
        result = evaluate(self.CREDIBLE, "Reuters")
        self.assertEqual(result["verdict"], "REAL")

    def test_borderline_article_is_suspicious(self):
        result = evaluate(
            "The council reportedly plans to change the rules next month.",
            "Local Herald")
        self.assertEqual(result["verdict"], "SUSPICIOUS")

    def test_report_contains_required_fields(self):
        result = evaluate(self.FABRICATED, "Unknown")
        for key in ("case_id", "verdict", "risk", "confidence",
                    "findings", "summary", "rules_checked"):
            self.assertIn(key, result)

    def test_every_finding_traces_to_a_registered_rule(self):
        registered = {r["id"] for r in RULES}
        result = evaluate(self.FABRICATED, "Unknown")
        for finding in result["findings"]:
            self.assertIn(finding["rule_id"], registered)

    def test_confidence_low_for_very_short_text(self):
        self.assertEqual(evaluate("Big news today.", "")["confidence"], "Low")

    def test_all_rules_are_uniquely_identified(self):
        ids = [r["id"] for r in RULES]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
