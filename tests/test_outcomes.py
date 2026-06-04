from datetime import date, timedelta

from core import PlannerData, TemplateBlock, Outcome, Day, OutcomeCheckin, Override, add_outcome, add_template_block, set_outcome_rating
from outcomes import trailing_window, pearson, block_done, confidence, MIN_DAYS, candidate_signals


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
