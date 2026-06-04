from datetime import date, timedelta

from core import PlannerData, TemplateBlock, Outcome, Day, OutcomeCheckin, Override, add_outcome, add_template_block, set_outcome_rating
from outcomes import trailing_window, pearson, block_done, confidence, MIN_DAYS, candidate_signals, select_signal, phrase, build_insight, Signal, _when


_CAUSAL = ["cause", "because", "improve", "proven", "makes you", "guarantee"]


def test_trailing_window_is_six_weeks_inclusive():
    start, end = trailing_window(date(2026, 6, 4))
    assert end == date(2026, 6, 4)
    assert (end - start).days == 41  # 42 days inclusive


def test_pearson_returns_none_on_zero_variance():
    assert pearson([1, 1, 1], [3, 4, 5]) is None      # x all-same
    assert pearson([1, 2, 3], [4, 4, 4]) is None      # y all-same
    assert pearson([1, 2], [3, 4]) is None            # n < 3


def test_pearson_perfect_positive():
    assert round(pearson([1, 2, 3], [2, 4, 6]), 3) == 1.0


def test_block_done_true_only_for_done_state():
    from core import Override
    data = PlannerData(days={"2026-06-02": Day(overrides={
        "08:00": Override(state="done"),
        "09:00": Override(state="skipped"),
    })})
    assert block_done(data, "2026-06-02", "08:00") is True
    assert block_done(data, "2026-06-02", "09:00") is False
    assert block_done(data, "2026-06-02", "10:00") is False  # no override
    assert block_done(data, "2026-06-09", "08:00") is False  # no day


def test_confidence_not_ready_below_threshold():
    data = PlannerData(
        template=[TemplateBlock(start="08:00", end="09:00", label="walk", id="b1")],
        outcomes=[Outcome(id="o1", name="Energy", description="",
                          direction="increase", created="2026-05-01",
                          status="active", block_ids=["b1"])],
    )
    conf = confidence(data, data.outcomes[0], date(2026, 6, 4))
    assert conf["ready"] is False
    assert conf["daysChecked"] == 0
    assert conf["completions"] == 0


def _energy_fixture():
    """Single linked morning block; energy is higher on days the block is done."""
    data = PlannerData()
    b = add_template_block(data, "08:00", "09:00", "deep work")
    o = add_outcome(data, "Energy", "", "increase", block_ids=[b.id], created="2026-04-01")
    base = date(2026, 6, 4)
    for i in range(21):                       # 21 days of data, well past threshold
        d = (base - timedelta(days=i)).isoformat()
        done = i % 2 == 0                      # alternate done/not
        if done:
            data.days.setdefault(d, Day()).overrides["08:00"] = Override(state="done")
        set_outcome_rating(data, d, o.id, 5 if done else 2, d + "T20:00")
    return data, o, b


def test_candidate_signals_finds_block_adherence_link():
    data, o, b = _energy_fixture()
    signals = candidate_signals(data, o, date(2026, 6, 4))
    block_sigs = [s for s in signals if s.kind == "block_daily" and s.block_id == b.id]
    assert block_sigs
    best = max(block_sigs, key=lambda s: s.strength)
    assert best.strength > 0.5
    assert best.mean_delta > 0                 # done days rate higher


def test_candidate_signals_skips_all_same_adherence():
    data = PlannerData()
    b = add_template_block(data, "08:00", "09:00", "walk")
    o = add_outcome(data, "Energy", "", "increase", block_ids=[b.id], created="2026-04-01")
    base = date(2026, 6, 4)
    for i in range(21):
        d = (base - timedelta(days=i)).isoformat()
        data.days.setdefault(d, Day()).overrides["08:00"] = Override(state="done")  # always done
        set_outcome_rating(data, d, o.id, (i % 5) + 1, "t")
    block_sigs = [s for s in candidate_signals(data, o, base) if s.block_id == b.id and s.kind == "block_daily"]
    assert block_sigs == []                    # zero variance -> no signal


def test_candidate_signals_empty_when_no_ratings():
    data = PlannerData()
    b = add_template_block(data, "08:00", "09:00", "walk")
    o = add_outcome(data, "Energy", "", "increase", block_ids=[b.id], created="2026-04-01")
    assert candidate_signals(data, o, date(2026, 6, 4)) == []


def test_candidate_signals_single_block_lagged_off_history_no_crash():
    data, o, b = _energy_fixture()
    # window start has no prior data; lag 1/2 reach off the edge — must not raise
    signals = candidate_signals(data, o, date(2026, 6, 4))
    assert all(s.lag in (0, 1, 2) for s in signals)


def test_phrase_is_cautious_and_non_causal():
    s = Signal(kind="block_daily", label="deep work", lag=0, threshold=1.0,
               mean_delta=1.2, strength=0.7, n=20, block_id="b1")
    card = phrase(s, Outcome(id="o1", name="Energy", description="",
                             direction="increase", created="x", status="active", block_ids=["b1"]))
    assert "Energy averaged +1.2" in card["headline"]
    assert "deep work" in card["headline"]
    assert card["suggestion"]["action"] == "keep"
    text = (card["headline"] + " " + card["suggestion"]["text"]).lower()
    assert not any(w in text for w in _CAUSAL)


def test_phrase_negative_late_end_suggests_tweak():
    s = Signal(kind="late_end_daily", label="blocks ending late", lag=0, threshold=21 * 60,
               mean_delta=-0.8, strength=0.6, n=20, block_id=None)
    card = phrase(s, Outcome(id="o1", name="Sleep", description="",
                             direction="increase", created="x", status="active", block_ids=[]))
    assert "ran lower" in card["headline"]
    assert "after 21:00" in card["headline"]
    assert card["suggestion"]["action"] == "tweak"


def test_select_signal_picks_strongest_over_threshold():
    weak = Signal("block_daily", "a", 0, 1.0, 0.5, 0.2, 20, "b1")
    strong = Signal("block_daily", "b", 0, 1.0, 0.9, 0.7, 20, "b2")
    assert select_signal([weak, strong]) is strong
    assert select_signal([weak]) is None        # below MIN_STRENGTH


def test_build_insight_returns_meter_below_threshold():
    data = PlannerData(outcomes=[Outcome(id="o1", name="Energy", description="",
                       direction="increase", created="x", status="active", block_ids=[])])
    card = build_insight(data, data.outcomes[0], date(2026, 6, 4))
    assert card["ready"] is False
    assert card["headline"] is None


def test_build_insight_null_result_is_empathetic():
    # Enough data to be "ready", but ratings are noise vs adherence -> no signal.
    data = PlannerData()
    b = add_template_block(data, "08:00", "09:00", "walk")
    o = add_outcome(data, "Energy", "", "increase", block_ids=[b.id], created="2026-04-01")
    base = date(2026, 6, 4)
    for i in range(21):
        d = (base - timedelta(days=i)).isoformat()
        if i % 2 == 0:
            data.days.setdefault(d, Day()).overrides["08:00"] = Override(state="done")
        set_outcome_rating(data, d, o.id, 3, "t")   # constant rating -> zero variance
    card = build_insight(data, o, base)
    assert card["ready"] is True
    assert card["meanDelta"] is None
    assert "No clear pattern yet" in card["headline"]
    assert card["suggestion"]["action"] == "tweak"


def test_when_phrasing_for_new_kinds():
    from outcomes import _when, Signal
    assert _when(Signal("afternoon_weekly", "afternoon blocks", 0, 3, 0, 0.5, 5, None)) == "on weeks with 3+ afternoon blocks"
    assert _when(Signal("evening_weekly", "evening blocks", 0, 2, 0, 0.5, 5, None)) == "on weeks with 2+ evening blocks"
    assert _when(Signal("dow_daily", "Saturday", 0, 1, 0, 0.5, 5, None)) == "on Saturdays"
    assert _when(Signal("duration_daily", "block time", 0, 90, 0, 0.5, 5, None)) == "on days with over 1.5h of your blocks"


def test_candidate_signals_detects_day_of_week():
    data = PlannerData()
    o = add_outcome(data, "Mood", "", "increase", created="2026-04-01")
    base = date(2026, 6, 4)
    for i in range(21):
        d = (base - timedelta(days=i)).isoformat()
        wd = date.fromisoformat(d).weekday()
        set_outcome_rating(data, d, o.id, 5 if wd == 5 else 2, "t")  # Saturdays high
    sigs = [s for s in candidate_signals(data, o, base) if s.kind == "dow_daily"]
    assert any(s.label == "Saturday" and s.mean_delta > 0 for s in sigs)


def test_candidate_signals_detects_duration():
    data = PlannerData()
    b = add_template_block(data, "08:00", "12:00", "long block")  # 4h block
    o = add_outcome(data, "Energy", "", "increase", block_ids=[b.id], created="2026-04-01")
    base = date(2026, 6, 4)
    for i in range(21):
        d = (base - timedelta(days=i)).isoformat()
        done = i % 2 == 0
        if done:
            data.days.setdefault(d, Day()).overrides["08:00"] = Override(state="done")
        set_outcome_rating(data, d, o.id, 5 if done else 2, "t")
    sigs = [s for s in candidate_signals(data, o, base) if s.kind == "duration_daily"]
    assert sigs and max(sigs, key=lambda s: s.strength).mean_delta > 0


def test_candidate_signals_detects_evening_bucket():
    data = PlannerData()
    b = add_template_block(data, "21:00", "22:00", "late work")  # evening block
    o = add_outcome(data, "Sleep", "", "increase", block_ids=[b.id], created="2026-04-01")
    base = date(2026, 6, 4)
    for i in range(28):
        d = (base - timedelta(days=i)).isoformat()
        done = i % 2 == 0
        if done:
            data.days.setdefault(d, Day()).overrides["21:00"] = Override(state="done")
        set_outcome_rating(data, d, o.id, 2 if done else 5, "t")  # late work -> worse sleep
    sigs = [s for s in candidate_signals(data, o, base) if s.kind == "evening_weekly"]
    assert sigs  # an evening-bucket weekly signal is produced
