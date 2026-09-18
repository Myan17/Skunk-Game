"""Pin the tournament benchmark's findings.

The README states measured win rates. These tests re-run a smaller seeded
tournament and assert the ordering and the confidence-interval verdicts, so a
strategy change that invalidates the published table fails CI.
"""
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "benchmarks"))

from tournament import ROSTER, head_to_head, run, wilson  # noqa: E402

GAMES = 4000
SEED = 17


@pytest.fixture(scope="module")
def result():
    return run(GAMES, SEED)


class TestWilsonInterval:
    def test_contains_the_point_estimate(self):
        lo, hi = wilson(570, 1000)
        assert lo < 0.57 < hi

    def test_narrows_with_more_games(self):
        lo_small, hi_small = wilson(57, 100)
        lo_big, hi_big = wilson(5700, 10000)
        assert (hi_big - lo_big) < (hi_small - lo_small)

    def test_stays_inside_zero_one_at_the_extremes(self):
        assert wilson(0, 50)[0] >= 0.0
        assert wilson(50, 50)[1] <= 1.0

    def test_zero_games_is_uninformative(self):
        assert wilson(0, 0) == (0.0, 1.0)


class TestPublishedFindings:
    def test_context_aware_ranks_first(self, result):
        ranked = sorted(result["overall"], key=lambda n: -result["overall"][n]["rate"])
        assert ranked[0] == "ContextAware"

    def test_random_ranks_last(self, result):
        ranked = sorted(result["overall"], key=lambda n: -result["overall"][n]["rate"])
        assert ranked[-1] == "Random(60%)"

    def test_expected_value_loses_to_context_aware_significantly(self, result):
        # The central finding: the points-optimal rule is not win-optimal.
        lo, hi = result["matrix"]["ExpectedValue"]["ContextAware"]["ci"]
        assert hi < 0.5

    def test_expected_value_is_indistinguishable_from_a_plain_threshold(self, result):
        lo, hi = result["matrix"]["ExpectedValue"]["Conservative(15)"]["ci"]
        assert lo <= 0.5 <= hi

    def test_expected_value_beats_aggressive_and_random(self, result):
        for opp in ("Aggressive(30)", "Random(60%)"):
            assert result["matrix"]["ExpectedValue"][opp]["ci"][0] > 0.5, opp

    def test_published_overall_rates(self, result):
        expected = {
            "ContextAware": 0.615,
            "ExpectedValue": 0.576,
            "Conservative(15)": 0.563,
            "FixedRoll(3)": 0.557,
            "Aggressive(30)": 0.489,
            "Random(60%)": 0.201,
        }
        for name, rate in expected.items():
            assert result["overall"][name]["rate"] == pytest.approx(rate, abs=0.001), name


class TestHarnessFairness:
    def test_matrix_is_zero_sum(self, result):
        for a in result["matrix"]:
            for b, r in result["matrix"][a].items():
                assert r["wins"] + result["matrix"][b][a]["wins"] == GAMES

    def test_seats_are_alternated(self):
        # A bot playing itself must land near 50%: any first-mover bias the
        # harness failed to cancel would show up here.
        random.seed(3)
        wins = head_to_head(ROSTER["ExpectedValue"], ROSTER["ExpectedValue"], 4000)
        lo, hi = wilson(wins, 4000)
        assert lo <= 0.5 <= hi

    def test_seeded_runs_are_reproducible(self):
        a = run(200, 99)
        b = run(200, 99)
        assert a["overall"] == b["overall"]
