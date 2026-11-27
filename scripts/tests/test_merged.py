"""Australia Merged (``merged.json``) — the year-in-review generator.

Two properties matter more than any individual figure here.

**No number is typed by hand.** Every card's wording is built from the `facts`
dict, so a sentence can never contradict the data behind it. The tests below
change the input and assert the copy moved with it.

**The quiz is winnable and honest.** Its answer has to be among its options,
its decoys have to be real matters with the outcome the question implies, and
the reveal has to name the right matter. A quiz that silently went wrong would
look fine on the page, which is exactly why it is pinned here.
"""

import datetime as dt

import pytest

from scripts.constants import merger_status
from scripts.generate.static_data.outputs import merged


AS_AT = dt.date(2026, 11, 27)
YEAR = 2026


def _matter(merger_id, name, *, filed, decided=None, determination=None,
            waiver=False, stage="Phase 1 - initial assessment", events=None,
            status=merger_status.ASSESSMENT_COMPLETED, **extra):
    return {
        "merger_id": merger_id,
        "merger_name": name,
        "is_waiver": waiver,
        "status": status,
        "stage": stage,
        "effective_notification_datetime": f"{filed}T12:00:00Z",
        "determination_publication_date": f"{decided}T12:00:00Z" if decided else None,
        "accc_determination": determination,
        "events": events or [],
        "acquirers": [],
        "targets": [],
        "other_parties": [],
        "anzsic_codes": [],
        **extra,
    }


@pytest.fixture
def register():
    """A small register with one of everything the deck talks about."""
    return [
        # Three cleared notifications, one of them the year's longest review.
        _matter("MN-00001", "Alpha – Beta", filed="2026-01-05", decided="2026-02-02",
                determination=merger_status.APPROVED),
        _matter("MN-00002", "Gamma – Delta", filed="2026-03-10", decided="2026-04-10",
                determination=merger_status.APPROVED),
        _matter("MN-00003", "Epsilon – Zeta", filed="2026-05-04", decided="2026-06-01",
                determination=merger_status.APPROVED),
        # A refusal, after phase 2 and after an extension.
        _matter(
            "MN-00004", "Eta – Theta", filed="2026-02-02", decided="2026-08-07",
            determination=merger_status.NOT_APPROVED,
            stage=merger_status.PHASE_2_STAGE,
            phase_1_determination=merger_status.REFERRED_TO_PHASE_2,
            phase_1_determination_date="2026-04-01T12:00:00Z",
            phase_2_determination=merger_status.NOT_APPROVED,
            events=[{
                "date": "2026-03-02T12:00:00Z",
                "title": "Timeline extended by 20 business days – following request by parties",
            }],
        ),
        # Two waivers, one of them decided the day after it was filed.
        _matter("WA-00005", "Iota – Kappa", filed="2026-04-06", decided="2026-04-07",
                determination=merger_status.APPROVED, waiver=True,
                stage="Waiver application"),
        _matter("WA-00006", "Lambda – Mu", filed="2026-06-01", decided="2026-06-22",
                determination=merger_status.NOT_APPROVED, waiver=True,
                stage="Waiver application"),
    ]


@pytest.fixture
def questionnaires():
    return {
        "MN-00001": {"questions_count": 3},
        "MN-00002": {"questions_count": 3},
        "MN-00003": {"questions_count": 3},
        "MN-00004": {"questions_count": 11},
    }


@pytest.fixture
def payload(register, questionnaires, monkeypatch):
    monkeypatch.setattr(merged, "FAMOUS_CLEARED_IDS", ("MN-00001", "MN-00002", "MN-00003"))
    return merged.generate(register, questionnaires, year=YEAR, today=AS_AT)


def card(payload, card_id):
    return next(c for c in payload["cards"] if c["id"] == card_id)


# --------------------------------------------------------------------------
# the file itself
# --------------------------------------------------------------------------

def test_says_what_it_covers_and_that_the_year_is_not_over(payload):
    assert payload["year"] == YEAR
    assert payload["as_at"] == AS_AT.isoformat()
    assert payload["complete"] is False
    assert "27 November 2026" in payload["coverage"]
    assert "not over" in payload["coverage"]


def test_a_finished_year_says_so(register, questionnaires, monkeypatch):
    monkeypatch.setattr(merged, "FAMOUS_CLEARED_IDS", ("MN-00001",))
    done = merged.generate(register, questionnaires, year=YEAR, today=dt.date(2026, 12, 31))
    assert done["complete"] is True
    assert "not over" not in done["coverage"]


def test_every_card_is_numbered_in_order(payload):
    assert [c["index"] for c in payload["cards"]] == list(range(1, len(payload["cards"]) + 1))


def test_card_ids_are_unique(payload):
    ids = [c["id"] for c in payload["cards"]]
    assert len(ids) == len(set(ids))


# --------------------------------------------------------------------------
# scope
# --------------------------------------------------------------------------

def test_counting_cards_use_the_years_intake(payload):
    """896-style figures count what was *filed* in the year."""
    volume = payload["facts"]["volume"]
    assert volume["matters"] == 6
    assert volume["notifications"] == 4
    assert volume["waivers"] == 2
    assert card(payload, "scale")["stat"] == 6


def test_narrative_cards_reach_back_to_earlier_filings(register, questionnaires, monkeypatch):
    """A 2025 filing refused in 2026 is part of 2026's story, not 2025's.

    This is the Coles – Kalgoorlie case: notified in the voluntary window, and
    then the most consequential matter of the regime's first year.
    """
    monkeypatch.setattr(merged, "FAMOUS_CLEARED_IDS", ("MN-00001",))
    register.append(_matter(
        "MN-09999", "Carryover – Matter", filed="2025-11-27", decided="2026-07-01",
        determination=merger_status.NOT_APPROVED, stage=merger_status.PHASE_2_STAGE,
        phase_2_determination=merger_status.NOT_APPROVED,
    ))
    payload = merged.generate(register, questionnaires, year=YEAR, today=AS_AT)

    # Not in the intake...
    assert payload["facts"]["volume"]["matters"] == 6
    # ...but in the refusals, and first, because it was decided first.
    refused = payload["facts"]["outcomes"]["refused"]
    assert [r["merger_id"] for r in refused] == ["MN-09999", "MN-00004"]


def test_a_refusal_hidden_by_a_public_benefit_application_still_counts():
    """A matter that applies for a public benefit determination reads as live
    again, so its refusal has no headline date. It is still a refusal."""
    register = [_matter(
        "MN-00010", "Nu – Xi", filed="2026-03-03", decided=None,
        determination=None, status=merger_status.UNDER_ASSESSMENT,
        stage=merger_status.PUBLIC_BENEFIT_STAGE,
        phase_2_determination=merger_status.NOT_APPROVED,
        phase_2_determination_date="2026-09-23T12:00:00Z",
    )]
    facts = merged.build_facts(register, {}, YEAR, AS_AT)
    assert [r["date"] for r in facts["outcomes"]["refused"]] == ["2026-09-23"]


# --------------------------------------------------------------------------
# the copy follows the data
# --------------------------------------------------------------------------

def test_headline_copy_quotes_the_computed_total(payload):
    assert "6 deals" in card(payload, "opening")["lede"]
    assert card(payload, "closing")["heading"] == "6 matters"


def test_changing_the_data_changes_the_sentence(register, questionnaires, monkeypatch):
    monkeypatch.setattr(merged, "FAMOUS_CLEARED_IDS", ("MN-00001",))
    before = merged.generate(register, questionnaires, year=YEAR, today=AS_AT)
    register.append(_matter("MN-00007", "Omicron – Pi", filed="2026-09-09",
                            decided="2026-10-09", determination=merger_status.APPROVED))
    after = merged.generate(register, questionnaires, year=YEAR, today=AS_AT)
    assert "6 deals" in card(before, "opening")["lede"]
    assert "7 deals" in card(after, "opening")["lede"]


def test_the_months_chart_marks_the_month_still_running(payload):
    months = card(payload, "months")["months"]
    assert [m["partial"] for m in months] == [False] * 10 + [True]
    assert months[-1]["month"] == AS_AT.month
    # Abbreviations label the axis; prose uses the full name.
    assert months[0]["label"] == "Jan"
    assert months[0]["name"] == "January"


def test_months_stop_at_the_cut_off(payload):
    assert max(m["month"] for m in card(payload, "months")["months"]) == AS_AT.month


def test_the_refusals_card_does_not_claim_phase_2_without_checking(register,
                                                                   questionnaires,
                                                                   monkeypatch):
    monkeypatch.setattr(merged, "FAMOUS_CLEARED_IDS", ("MN-00001",))
    register.append(_matter("MN-00008", "Rho – Sigma", filed="2026-05-05",
                            decided="2026-06-05", determination=merger_status.NOT_APPROVED))
    heading = card(merged.generate(register, questionnaires, year=YEAR, today=AS_AT),
                   "refusals")["heading"]
    assert "Every one had been through phase 2" not in heading
    assert "1 of them after phase 2" in heading


def test_lists_read_as_sentences():
    assert merged._join([]) == ""
    assert merged._join(["a"]) == "a"
    assert merged._join(["a", "b"]) == "a and b"
    assert merged._join(["a", "b", "c"]) == "a, b and c"


def test_a_whole_median_is_not_written_as_a_decimal():
    assert merged._median([3, 3, 3, 3]) == 3
    assert isinstance(merged._median([3, 3, 3, 3]), int)
    assert merged._median([3, 4]) == 3.5


# --------------------------------------------------------------------------
# the quiz
# --------------------------------------------------------------------------

def test_every_quiz_answer_is_one_of_its_options(payload):
    quizzes = [c for c in payload["cards"] if c["kind"] == "quiz"]
    assert quizzes
    for quiz in quizzes:
        keys = [o["key"] for o in quiz["options"]]
        assert quiz["answer"] in keys, f"{quiz['id']} has no winning option"
        assert len(keys) == len(set(keys)), f"{quiz['id']} repeats an option"
        assert len(keys) >= 3, f"{quiz['id']} is a coin flip"


def test_quiz_cards_are_numbered_against_the_total(payload):
    quizzes = [c for c in payload["cards"] if c["kind"] == "quiz"]
    assert payload["quiz_total"] == len(quizzes)
    for position, quiz in enumerate(quizzes, start=1):
        assert quiz["eyebrow"].endswith(f"{position} of {payload['quiz_total']}")


def test_the_longest_review_quiz_answers_with_the_longest_review(payload):
    quiz = card(payload, "quiz-longest")
    longest = payload["facts"]["durations"]["longest_concluded"]
    assert quiz["answer"] == longest[0]["merger_id"]
    assert str(longest[0]["business_days"]) in quiz["body"][0]
    # The decoys are the real runners-up, so elimination doesn't work.
    assert [o["key"] for o in quiz["options"]] == [r["merger_id"] for r in longest]


def test_the_refusal_quiz_decoys_must_really_have_been_cleared(register, monkeypatch):
    monkeypatch.setattr(merged, "FAMOUS_CLEARED_IDS", ("MN-00004",))  # a refusal
    with pytest.raises(ValueError, match="cleared decoy"):
        merged.generate(register, {}, year=YEAR, today=AS_AT)


def test_the_refusal_quiz_decoys_must_exist(register, monkeypatch):
    monkeypatch.setattr(merged, "FAMOUS_CLEARED_IDS", ("MN-NOPE",))
    with pytest.raises(ValueError, match="not .*on the register"):
        merged.generate(register, {}, year=YEAR, today=AS_AT)


def test_the_refusal_quiz_decoys_must_be_from_the_year(register, monkeypatch):
    register.append(_matter("MN-00009", "Tau – Upsilon", filed="2025-01-05",
                            decided="2025-02-05", determination=merger_status.APPROVED))
    monkeypatch.setattr(merged, "FAMOUS_CLEARED_IDS", ("MN-00009",))
    with pytest.raises(ValueError, match="not in 2026"):
        merged.generate(register, {}, year=YEAR, today=AS_AT)


def test_the_questionnaire_options_bracket_the_real_answer():
    options = [int(o["key"]) for o in merged._question_options(16)]
    assert 16 in options
    assert len(options) == len(set(options))
    assert min(options) < 16 < max(options)


# --------------------------------------------------------------------------
# facts worth pinning
# --------------------------------------------------------------------------

def test_business_day_figures_use_the_accc_calendar(payload):
    """Not a plain weekday count: the statutory clock skips ACT public
    holidays and the 23 December – 10 January shutdown."""
    volume = payload["facts"]["volume"]
    # 2026 to 27 November has 240 weekdays; the ACCC calendar has fewer.
    assert volume["business_days"] < 240
    assert volume["per_business_day"] == round(6 / volume["business_days"], 1)


def test_the_fastest_waiver_is_reported_with_both_its_dates(payload):
    durations = payload["facts"]["durations"]
    assert durations["fastest_waiver"]["merger_id"] == "WA-00005"
    assert durations["fastest_waiver"]["business_days"] == 1
    assert durations["fastest_waiver_filed"] == "2026-04-06"
    assert durations["fastest_waiver_decided"] == "2026-04-07"


def test_waivers_and_notifications_are_counted_apart(payload):
    outcomes = payload["facts"]["outcomes"]
    assert outcomes["waivers_decided"] == 2
    assert outcomes["waivers_declined"] == 1
    assert outcomes["waiver_grant_rate_pct"] == 50.0
    # The one refused notification is not in the waiver figures.
    assert outcomes["notifications_decided"] == 4


def test_an_extension_is_attributed_to_whoever_asked_for_it(payload):
    extensions = payload["facts"]["extensions"]
    assert extensions["events"] == 1
    assert extensions["total_bd"] == 20
    assert extensions["by_parties"] == 1
    assert extensions["by_accc"] == 0


def test_the_personal_card_carries_an_empty_state(payload):
    personal = card(payload, "personal" if False else "your-year")
    assert personal["kind"] == "personal"
    assert personal["empty_heading"]
    assert personal["empty_body"]


def test_no_card_is_left_without_something_to_show(payload):
    for c in payload["cards"]:
        has_content = any(
            c.get(field) for field in
            ("heading", "lede", "body", "rows", "timeline", "months", "question", "figures")
        )
        assert has_content, f"card {c['id']} would render empty"
