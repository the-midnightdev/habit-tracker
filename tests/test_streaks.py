from datetime import date

from habit_core import current_streak, longest_streak, completion_pct_30d


T = date(2026, 5, 14)  # fixed "today" for these tests


def test_current_streak_empty():
    assert current_streak([], today=T) == 0


def test_current_streak_only_today():
    assert current_streak(["2026-05-14"], today=T) == 1


def test_current_streak_today_and_yesterday():
    assert current_streak(["2026-05-13", "2026-05-14"], today=T) == 2


def test_current_streak_yesterday_only_does_not_break():
    # Today not yet marked; streak counts back from yesterday.
    assert current_streak(["2026-05-13"], today=T) == 1


def test_current_streak_yesterday_and_day_before():
    assert current_streak(["2026-05-12", "2026-05-13"], today=T) == 2


def test_current_streak_breaks_after_full_day_skipped():
    # Day before yesterday only — yesterday was skipped.
    assert current_streak(["2026-05-12"], today=T) == 0


def test_current_streak_ignores_future_dates():
    assert current_streak(["2026-05-20"], today=T) == 0


def test_longest_streak_empty():
    assert longest_streak([]) == 0


def test_longest_streak_single_run():
    assert longest_streak(["2026-05-12", "2026-05-13", "2026-05-14"]) == 3


def test_longest_streak_picks_max_run():
    completions = [
        "2026-04-01", "2026-04-02",                         # run of 2
        "2026-04-10", "2026-04-11", "2026-04-12", "2026-04-13",  # run of 4
        "2026-05-14",                                       # run of 1
    ]
    assert longest_streak(completions) == 4


def test_completion_pct_30d_empty():
    assert completion_pct_30d([], today=T) == 0


def test_completion_pct_30d_full():
    completions = [
        (date.fromordinal(T.toordinal() - i)).isoformat() for i in range(30)
    ]
    assert completion_pct_30d(completions, today=T) == 100


def test_completion_pct_30d_half():
    completions = [
        (date.fromordinal(T.toordinal() - i)).isoformat() for i in range(0, 30, 2)
    ]
    assert completion_pct_30d(completions, today=T) == 50


def test_completion_pct_30d_ignores_old_dates():
    completions = ["2025-01-01", "2025-01-02"]
    assert completion_pct_30d(completions, today=T) == 0
