from datetime import date

from core import PlannerData, TemplateBlock, Outcome, Day, OutcomeCheckin
from outcomes import trailing_window, pearson, block_done, confidence, MIN_DAYS


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
