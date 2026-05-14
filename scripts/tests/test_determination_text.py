"""Tests for determination_text cleaning heuristics.

These mirror the JS heuristics in
merger-tracker/frontend/src/components/DeterminationExplanationSection.jsx.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from determination_text import clean_explanation, clean_label, clean_merger


# ---------------------------------------------------------------------------
# clean_label
# ---------------------------------------------------------------------------

class TestCleanLabel:
    def test_collapses_internal_newline(self):
        assert clean_label("Explanation for\ndetermination") == "Explanation for determination"

    def test_collapses_multiple_whitespace(self):
        assert clean_label("Parties to the\n  Acquisition") == "Parties to the Acquisition"

    def test_strips_leading_trailing(self):
        assert clean_label("  Determination  ") == "Determination"

    def test_no_change_when_clean(self):
        assert clean_label("Acquisition") == "Acquisition"

    def test_passthrough_non_string(self):
        assert clean_label(None) is None


# ---------------------------------------------------------------------------
# clean_explanation
# ---------------------------------------------------------------------------

class TestCleanExplanation:
    def test_layout_newline_becomes_space(self):
        text = "The ACCC has considered the\ninformation provided."
        assert clean_explanation(text) == "The ACCC has considered the information provided."

    def test_hyphen_word_wrap_joins_directly(self):
        # "post-\nacquisition" should become "post-acquisition", not "post- acquisition".
        assert clean_explanation("post-\nacquisition") == "post-acquisition"

    def test_sentence_boundary_promotes_to_paragraph(self):
        # ". " then capital letter at start of next line -> real paragraph break.
        text = "competition.\nIn particular:"
        assert clean_explanation(text) == "competition.\n\nIn particular:"

    def test_close_paren_then_capital_promotes_to_paragraph(self):
        text = "(the Act).\nBased on"
        assert clean_explanation(text) == "(the Act).\n\nBased on"

    def test_lowercase_after_period_stays_layout(self):
        # ". " then lowercase next line is unusual but stays a layout break.
        text = "etc.\nfoo bar"
        assert clean_explanation(text) == "etc. foo bar"

    def test_bullet_promotes_to_paragraph(self):
        text = "the parties:\n• first item\n• second item"
        result = clean_explanation(text)
        assert "\n\n• first item" in result
        assert "\n\n• second item" in result

    def test_lettered_list_promotes_to_paragraph(self):
        text = "considers:\na. first reason\nb. second reason"
        result = clean_explanation(text)
        assert "\n\na. first reason" in result
        assert "\n\nb. second reason" in result

    def test_uppercase_without_terminator_stays_layout(self):
        # No "." or ")" before -> just a wrap, even if next line starts uppercase.
        text = "the Australian\nCompetition and Consumer Commission"
        assert clean_explanation(text) == "the Australian Competition and Consumer Commission"

    def test_empty_string(self):
        assert clean_explanation("") == ""

    def test_no_newlines_unchanged(self):
        assert clean_explanation("plain text") == "plain text"

    def test_passthrough_non_string(self):
        assert clean_explanation(None) is None

    def test_wa95015_explanation_sample(self):
        # Realistic excerpt from WA-95015.
        text = (
            "In making this notification waiver determination, the Australian\n"
            "Competition and Consumer Commission (the ACCC) has considered\n"
            "the information provided with the notification waiver application and\n"
            "had regard to the factors in section 51ABV(2)(b) of the Competition\n"
            "and Consumer Act 2010 (Cth) (the Act).\n"
            "Based on the information provided in the application, the ACCC\n"
            "considers that the Acquisition is unlikely to give rise to any material\n"
            "lessening of competition."
        )
        out = clean_explanation(text)
        # No more single newlines in the body.
        assert "Australian Competition" in out
        assert "Act).\n\nBased on" in out
        # And no orphaned newlines in the first paragraph.
        first_para = out.split("\n\n")[0]
        assert "\n" not in first_para


# ---------------------------------------------------------------------------
# clean_merger
# ---------------------------------------------------------------------------

class TestCleanMerger:
    def test_cleans_table_content_on_each_event(self):
        merger = {
            "merger_id": "WA-95015",
            "events": [
                {
                    "determination_table_content": [
                        {
                            "item": "Explanation for\ndetermination",
                            "details": "The ACCC has\nconsidered the application.",
                        },
                        {
                            "item": "Date of determination",
                            "details": "11 May 2026",
                        },
                    ]
                }
            ],
        }
        clean_merger(merger)
        rows = merger["events"][0]["determination_table_content"]
        assert rows[0]["item"] == "Explanation for determination"
        assert rows[0]["details"] == "The ACCC has considered the application."
        assert rows[1]["item"] == "Date of determination"
        assert rows[1]["details"] == "11 May 2026"

    def test_handles_missing_events(self):
        merger = {"merger_id": "MN-30009"}
        # Should not raise.
        clean_merger(merger)
        assert merger == {"merger_id": "MN-30009"}

    def test_handles_empty_table_content(self):
        merger = {"events": [{"determination_table_content": []}]}
        clean_merger(merger)
        assert merger["events"][0]["determination_table_content"] == []

    def test_handles_non_dict_row(self):
        merger = {"events": [{"determination_table_content": ["not a dict"]}]}
        # Should not raise.
        clean_merger(merger)
        assert merger["events"][0]["determination_table_content"] == ["not a dict"]

    def test_leaves_other_fields_untouched(self):
        merger = {
            "merger_id": "MN-30009",
            "merger_name": "Daikin – AAMS",
            "events": [
                {
                    "stage": "Phase 1",
                    "determination_table_content": [
                        {"item": "Parties to the\nAcquisition", "details": "Daikin\nand AAMS"}
                    ],
                }
            ],
        }
        clean_merger(merger)
        assert merger["merger_name"] == "Daikin – AAMS"
        assert merger["events"][0]["stage"] == "Phase 1"
