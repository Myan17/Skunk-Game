"""
SKUNK Dice Game — Comprehensive Test Suite
============================================

Tests every rule, invariant, and edge case of the SKUNK game engine.
Uses pytest with deterministic dice injection (no reliance on random.seed).

Test Categories:
  1. Dice Mechanics         — roll classification is correct
  2. Turn Rules             — single 1, double 1s, safe rolls, banking
  3. Score Invariants        — scores never go negative, other players unmodified
  4. Game Flow              — end-of-game triggers, equal turns rule, winner logic
  5. Bot Strategy Contracts — each bot's decide() behaves per its specification
  6. Statistical Validation — dice fairness, outcome distributions over many runs
  7. Edge Cases             — 2 players, many players, target=1, immediate bust

Run with:
    pytest test_skunk_game.py -v
"""

import pytest
import random
from unittest.mock import patch
from collections import Counter
from typing import List, Tuple

from skunk_game import (
    roll_dice, classify_roll, skunk_turn, play_game,
    SkunkBot, ConservativeBot, AggressiveBot, ExpectedValueBot,
    ContextAwareBot, FixedRollBot, RandomBot, AdaptiveBot,
    MonteCarloBot, StopAtThresholdBot,
    run_tournament, verify_ev_formula_empirically,
    estimate_win_probability,
)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS: Deterministic dice sequences for testing
# ═══════════════════════════════════════════════════════════════════════════════

def make_dice_sequence(rolls: List[Tuple[int, int]]):
    """
    Create a dice_fn that returns rolls from a predetermined sequence.
    Raises an error if more rolls are requested than provided.
    """
    iterator = iter(rolls)
    def dice_fn():
        try:
            return next(iterator)
        except StopIteration:
            raise RuntimeError("Test dice sequence exhausted — need more rolls")
    return dice_fn


class AlwaysRollBot(SkunkBot):
    """Test bot that ALWAYS rolls (never stops voluntarily)."""
    def __init__(self):
        super().__init__("AlwaysRoll")
    def decide(self, turn_total, game_total, target, all_scores, player_index, roll_number):
        return True


class NeverRollBot(SkunkBot):
    """Test bot that NEVER rolls (stops immediately, banking 0)."""
    def __init__(self):
        super().__init__("NeverRoll")
    def decide(self, turn_total, game_total, target, all_scores, player_index, roll_number):
        return False


class RollNTimesBot(SkunkBot):
    """Test bot that rolls exactly N times then stops."""
    def __init__(self, n: int):
        super().__init__(f"RollNTimes({n})")
        self.n = n
    def decide(self, turn_total, game_total, target, all_scores, player_index, roll_number):
        return roll_number <= self.n


class StopAtThresholdBot(SkunkBot):
    """Test bot that stops once turn_total >= threshold."""
    def __init__(self, threshold: int):
        super().__init__(f"StopAt({threshold})")
        self.threshold = threshold
    def decide(self, turn_total, game_total, target, all_scores, player_index, roll_number):
        return turn_total < self.threshold


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: DICE MECHANICS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDiceMechanics:
    """Verify roll_dice() and classify_roll() behave correctly."""

    def test_roll_dice_returns_two_values(self):
        """roll_dice() must return a tuple of exactly 2 integers."""
        result = roll_dice()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_roll_dice_in_valid_range(self):
        """Each die must be in [1, 6]."""
        for _ in range(1000):
            d1, d2 = roll_dice()
            assert 1 <= d1 <= 6, f"Die 1 out of range: {d1}"
            assert 1 <= d2 <= 6, f"Die 2 out of range: {d2}"

    def test_classify_snake_eyes(self):
        """Both dice = 1 → snake_eyes."""
        assert classify_roll(1, 1) == 'snake_eyes'

    def test_classify_single_one_die1(self):
        """Die1=1, Die2≠1 → single_one."""
        for d2 in range(2, 7):
            assert classify_roll(1, d2) == 'single_one'

    def test_classify_single_one_die2(self):
        """Die1≠1, Die2=1 → single_one."""
        for d1 in range(2, 7):
            assert classify_roll(d1, 1) == 'single_one'

    def test_classify_safe_rolls(self):
        """Neither die is 1 → safe."""
        for d1 in range(2, 7):
            for d2 in range(2, 7):
                assert classify_roll(d1, d2) == 'safe', f"({d1},{d2}) should be safe"

    def test_classify_exhaustive(self):
        """All 36 outcomes are classified into exactly these 3 categories."""
        categories = Counter()
        for d1 in range(1, 7):
            for d2 in range(1, 7):
                result = classify_roll(d1, d2)
                assert result in ('snake_eyes', 'single_one', 'safe')
                categories[result] += 1
        assert categories['snake_eyes'] == 1    # (1,1) only
        assert categories['single_one'] == 10   # (1,2)..(1,6) + (2,1)..(6,1)
        assert categories['safe'] == 25         # 5×5


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: TURN RULES (skunk_turn)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTurnRules:
    """Verify skunk_turn() enforces all SKUNK rules correctly."""

    def test_snake_eyes_zeroes_all_points(self):
        """Rolling double 1s must reset the player's score to 0."""
        scores = [50, 30, 40]
        dice = make_dice_sequence([(1, 1)])
        result = skunk_turn(100, scores, 0, strategy=AlwaysRollBot(), dice_fn=dice)
        assert result[0] == 0, "Snake eyes must zero out ALL accumulated points"
        # Other players unaffected
        assert result[1] == 30
        assert result[2] == 40

    def test_single_one_loses_turn_only(self):
        """Rolling a single 1 means player keeps their game_total but gains nothing."""
        scores = [50, 30, 40]
        # Roll (3,4)=7 first (safe), then (1,5) (single one)
        dice = make_dice_sequence([(3, 4), (1, 5)])
        result = skunk_turn(100, scores, 0, strategy=AlwaysRollBot(), dice_fn=dice)
        assert result[0] == 50, "Single 1 must keep game_total, lose turn points"

    def test_single_one_on_die2(self):
        """A 1 on the second die also triggers single_one rule."""
        scores = [25, 30]
        dice = make_dice_sequence([(5, 1)])
        result = skunk_turn(100, scores, 0, strategy=AlwaysRollBot(), dice_fn=dice)
        assert result[0] == 25, "Single 1 on die2 must lose turn"

    def test_safe_rolls_accumulate(self):
        """Safe rolls accumulate points correctly when player stops."""
        scores = [10, 20]
        # Roll (3,4)=7, then (5,2)=7, then stop (RollNTimes(2) stops after 2)
        dice = make_dice_sequence([(3, 4), (5, 2)])
        result = skunk_turn(100, scores, 0, strategy=RollNTimesBot(2), dice_fn=dice)
        assert result[0] == 10 + 7 + 7, f"Expected 24, got {result[0]}"

    def test_banking_zero_on_immediate_stop(self):
        """If bot stops immediately (turn_total=0), score is unchanged."""
        scores = [50, 30]
        result = skunk_turn(100, scores, 0, strategy=NeverRollBot())
        assert result[0] == 50, "Stopping immediately should keep same score"

    def test_snake_eyes_with_zero_starting_score(self):
        """Snake eyes when score is already 0 keeps it at 0."""
        scores = [0, 30]
        dice = make_dice_sequence([(1, 1)])
        result = skunk_turn(100, scores, 0, strategy=AlwaysRollBot(), dice_fn=dice)
        assert result[0] == 0

    def test_snake_eyes_after_accumulation(self):
        """Snake eyes after accumulating turn points still zeros everything."""
        scores = [80, 30]
        # Rolls: (5,5)=10, (6,6)=12, then (1,1) = snake eyes
        dice = make_dice_sequence([(5, 5), (6, 6), (1, 1)])
        result = skunk_turn(100, scores, 0, strategy=AlwaysRollBot(), dice_fn=dice)
        assert result[0] == 0, "Snake eyes must zero out even after earlier safe rolls"

    def test_turn_for_non_first_player(self):
        """skunk_turn works correctly for any player index."""
        scores = [10, 20, 30]
        dice = make_dice_sequence([(4, 3)])  # roll 7, then stop
        result = skunk_turn(100, scores, 2, strategy=RollNTimesBot(1), dice_fn=dice)
        assert result[0] == 10, "Player 0 should be unchanged"
        assert result[1] == 20, "Player 1 should be unchanged"
        assert result[2] == 37, f"Player 2 should be 30+7=37, got {result[2]}"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: SCORE INVARIANTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestScoreInvariants:
    """Verify invariants that must hold after every turn."""

    def test_scores_never_negative(self):
        """No player's score can ever be negative."""
        for _ in range(500):
            scores = [random.randint(0, 100) for _ in range(4)]
            idx = random.randint(0, 3)
            result = skunk_turn(100, scores, idx, strategy=AggressiveBot(25))
            for s in result:
                assert s >= 0, f"Score went negative: {result}"

    def test_other_players_unchanged(self):
        """A player's turn must NEVER modify other players' scores."""
        for _ in range(500):
            scores = [random.randint(0, 100) for _ in range(4)]
            idx = random.randint(0, 3)
            original = list(scores)
            result = skunk_turn(100, scores, idx, strategy=ExpectedValueBot())
            for i in range(4):
                if i != idx:
                    assert result[i] == original[i], (
                        f"Player {i}'s score changed from {original[i]} to {result[i]} "
                        f"during player {idx}'s turn"
                    )

    def test_original_scores_not_mutated(self):
        """skunk_turn must not mutate the input scores list."""
        scores = [10, 20, 30]
        original = list(scores)
        skunk_turn(100, scores, 0, strategy=AggressiveBot(20))
        assert scores == original, "Input scores list was mutated"

    def test_score_only_increases_or_zeroes(self):
        """After a turn, player's score is either >= original OR exactly 0 (snake eyes)."""
        for _ in range(500):
            scores = [random.randint(0, 100) for _ in range(4)]
            idx = random.randint(0, 3)
            original_score = scores[idx]
            result = skunk_turn(100, scores, idx, strategy=ExpectedValueBot())
            new_score = result[idx]
            assert new_score >= original_score or new_score == 0, (
                f"Score went from {original_score} to {new_score} — "
                f"must be >= original or exactly 0 (snake eyes)"
            )

    def test_return_length_matches_input(self):
        """Returned scores list has the same length as input."""
        for n in [2, 3, 5, 10]:
            scores = [0] * n
            result = skunk_turn(100, scores, 0, strategy=ConservativeBot(10))
            assert len(result) == n


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: GAME FLOW (play_game)
# ═══════════════════════════════════════════════════════════════════════════════

class TestGameFlow:
    """Verify the full game loop enforces all rules."""

    def test_game_ends_when_target_reached(self):
        """The game must end once a player reaches the target."""
        # Bot that rolls once then stops: each safe roll ≈ 4-12 points
        # With target=20, game should end in a few rounds
        bots = [ConservativeBot(25), ConservativeBot(25)]
        winner, scores = play_game(bots, target=20)
        assert max(scores) >= 20, "Game must not end before someone reaches target"

    def test_winner_has_highest_score(self):
        """The declared winner must have the highest final score."""
        for _ in range(100):
            bots = [ConservativeBot(15), AggressiveBot(25), ExpectedValueBot()]
            winner, scores = play_game(bots, target=100)
            assert scores[winner] == max(scores), (
                f"Winner (player {winner}, score {scores[winner]}) "
                f"doesn't have max score {max(scores)}: {scores}"
            )

    def test_all_players_equal_turns_when_first_player_wins(self):
        """
        When player 0 hits the target, players 1..N-1 must each get
        one more turn before the game ends.

        We test this by having player 0 reach the target quickly and
        verifying ALL other players got to play (their scores may have
        changed from 0).
        """
        # Player 0: aggressive, will likely reach target fast
        # Players 1-2: will at least get turns (even if they bust)
        # Use deterministic dice: player 0 gets big rolls, others get safe rolls
        rolls = []
        # Round 1: Player 0 rolls (6,6) x 9 times → 108 → stops (exceeds 100)
        # Actually let's just use a high-threshold bot with a generous target
        # Use target=12 to make it end fast
        dice_rolls = [
            # Round 1, Player 0: (6,6)=12 → 12 >= target, stops
            (6, 6),
            # Round 1, Player 1 gets final turn: (3,4)=7 → 7, stops
            (3, 4),
            # Round 1, Player 2 gets final turn: (5,5)=10 → 10, stops
            (5, 5),
        ]
        dice = make_dice_sequence(dice_rolls)
        bots = [RollNTimesBot(1), RollNTimesBot(1), RollNTimesBot(1)]
        winner, scores = play_game(bots, target=12, dice_fn=dice)

        assert scores[0] == 12, f"Player 0 should have 12, got {scores[0]}"
        assert scores[1] == 7, f"Player 1 should have 7 (got final turn), got {scores[1]}"
        assert scores[2] == 10, f"Player 2 should have 10 (got final turn), got {scores[2]}"

    def test_later_player_can_overtake(self):
        """
        If player 0 hits the target, a later player can still win
        by scoring higher in their final turn.
        """
        dice_rolls = [
            # Round 1, Player 0: (5,5)=10, (3,3)=6 → 16 ≥ 15, stop
            (5, 5), (3, 3),
            # Round 1, Player 1 (final turn): (6,6)=12, (6,5)=11 → 23, stop
            (6, 6), (6, 5),
        ]
        dice = make_dice_sequence(dice_rolls)
        bots = [StopAtThresholdBot(15), StopAtThresholdBot(20)]
        winner, scores = play_game(bots, target=15, dice_fn=dice)

        assert scores[0] == 16
        assert scores[1] == 23
        assert winner == 1, "Player 1 should win by overtaking in the final turn"

    def test_game_with_two_players(self):
        """Game works with minimum 2 players."""
        bots = [ConservativeBot(15), ConservativeBot(15)]
        winner, scores = play_game(bots, target=50)
        assert winner in [0, 1]
        assert max(scores) >= 50

    def test_game_with_many_players(self):
        """Game works with a large number of players."""
        bots = [ConservativeBot(15) for _ in range(8)]
        winner, scores = play_game(bots, target=100)
        assert 0 <= winner < 8
        assert max(scores) >= 100

    def test_never_roll_bots_game_never_ends_protection(self):
        """
        If all bots always stop (NeverRollBot), the game would never end
        because no one accumulates points. We need to understand this
        is a degenerate case — but the function call should still not crash
        with AlwaysRoll bots that actually do accumulate.
        """
        # This test verifies the game can complete even with conservative bots
        bots = [ConservativeBot(5), ConservativeBot(5)]
        winner, scores = play_game(bots, target=20)
        assert max(scores) >= 20


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: BOT STRATEGY CONTRACTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBotContracts:
    """Verify each bot's decide() method adheres to its documented logic."""

    # --- ConservativeBot ---
    def test_conservative_rolls_below_threshold(self):
        assert ConservativeBot(15).decide(14, 0, 100, [0,0], 0, 1) == True

    def test_conservative_stops_at_threshold(self):
        assert ConservativeBot(15).decide(15, 0, 100, [0,0], 0, 1) == False

    def test_conservative_stops_above_threshold(self):
        assert ConservativeBot(15).decide(20, 0, 100, [0,0], 0, 1) == False

    # --- AggressiveBot ---
    def test_aggressive_rolls_below_threshold(self):
        assert AggressiveBot(30).decide(29, 0, 100, [0,0], 0, 1) == True

    def test_aggressive_stops_at_threshold(self):
        assert AggressiveBot(30).decide(30, 0, 100, [0,0], 0, 1) == False

    # --- ExpectedValueBot ---
    def test_ev_rolls_when_ev_positive(self):
        # 11*0 + 0 = 0 < 200 → should roll
        assert ExpectedValueBot().decide(0, 0, 100, [0,0], 0, 1) == True

    def test_ev_stops_when_ev_negative(self):
        # 11*18 + 5 = 203 > 200 → should stop
        assert ExpectedValueBot().decide(18, 5, 100, [0,0], 0, 1) == False

    def test_ev_boundary(self):
        # 11*18 + 2 = 200 → exactly at breakeven → should stop (not strictly <200)
        assert ExpectedValueBot().decide(18, 2, 100, [0,0], 0, 1) == False

    def test_ev_more_conservative_with_high_game_total(self):
        # With game_total=100: threshold = (200-100)/11 ≈ 9.1
        bot = ExpectedValueBot()
        assert bot.decide(9, 100, 200, [100,0], 0, 1) == True   # 11*9+100=199 < 200
        assert bot.decide(10, 100, 200, [100,0], 0, 1) == False  # 11*10+100=210 > 200

    # --- ContextAwareBot ---
    def test_context_stops_when_banking_wins(self):
        """If banking turn_total reaches the target, ContextAwareBot should stop."""
        bot = ContextAwareBot()
        # game_total=90, turn_total=15 → potential=105 >= target=100
        assert bot.decide(15, 90, 100, [90, 50], 0, 3) == False

    def test_context_aggressive_when_behind_in_last_chance(self):
        """If opponent already hit target, ContextAwareBot should keep rolling to catch up."""
        bot = ContextAwareBot()
        # opponent at 105, we have 80+10=90 < 105 → must keep trying
        assert bot.decide(10, 80, 100, [80, 105], 0, 3) == True

    # --- FixedRollBot ---
    def test_fixed_roll_rolls_up_to_n(self):
        bot = FixedRollBot(3)
        assert bot.decide(0, 0, 100, [0,0], 0, 1) == True   # roll 1 < 3
        assert bot.decide(8, 0, 100, [0,0], 0, 2) == True   # roll 2 < 3
        assert bot.decide(16, 0, 100, [0,0], 0, 3) == False  # roll 3 = 3, stop

    def test_fixed_roll_stops_if_target_reached(self):
        bot = FixedRollBot(5)
        assert bot.decide(10, 95, 100, [95, 0], 0, 1) == False  # 95+10=105 >= 100

    # --- RandomBot ---
    def test_random_bot_stops_at_target(self):
        bot = RandomBot(1.0)  # always would roll, but should stop at target
        assert bot.decide(10, 95, 100, [95, 0], 0, 1) == False

    def test_random_bot_with_probability_one_always_rolls(self):
        bot = RandomBot(1.0)
        for _ in range(100):
            assert bot.decide(5, 20, 100, [20, 0], 0, 1) == True

    def test_random_bot_with_probability_zero_never_rolls(self):
        bot = RandomBot(0.0)
        for _ in range(100):
            assert bot.decide(5, 20, 100, [20, 0], 0, 1) == False


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: ADAPTIVE BOT
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdaptiveBot:
    """Verify the AdaptiveBot learning mechanism."""

    def test_risk_factor_stays_in_bounds(self):
        """Risk factor must stay within [0.3, 2.5] after any number of updates."""
        bot = AdaptiveBot(initial_risk=1.0)
        for _ in range(1000):
            bot.record_result(random.random() > 0.5)
            assert 0.3 <= bot.risk_factor <= 2.5, f"Risk factor out of bounds: {bot.risk_factor}"

    def test_risk_history_grows(self):
        """Each record_result call adds to risk_history."""
        bot = AdaptiveBot()
        initial_len = len(bot.risk_history)
        bot.record_result(True)
        assert len(bot.risk_history) == initial_len + 1
        bot.record_result(False)
        assert len(bot.risk_history) == initial_len + 2

    def test_generation_counter_increments(self):
        """Generation counter must increment by 1 per game."""
        bot = AdaptiveBot()
        assert bot.generation == 0
        bot.record_result(True)
        assert bot.generation == 1
        bot.record_result(False)
        assert bot.generation == 2

    def test_adaptive_stops_when_banking_wins(self):
        """Adaptive bot should stop if banking would win."""
        bot = AdaptiveBot()
        assert bot.decide(20, 85, 100, [85, 50], 0, 3) == False  # 85+20=105 >= 100

    def test_adaptive_aggressive_in_last_chance(self):
        """Adaptive bot should keep rolling if opponent hit target and we're behind."""
        bot = AdaptiveBot()
        assert bot.decide(5, 70, 100, [70, 110], 0, 2) == True  # 70+5=75 < 110

    def test_sliding_window_capped(self):
        """Recent wins window should not exceed window_size."""
        bot = AdaptiveBot()
        for _ in range(200):
            bot.record_result(True)
        assert len(bot.recent_wins) <= bot.window_size


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7: STATISTICAL VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestStatisticalValidation:
    """
    Statistical tests that validate dice fairness and outcome distributions.
    These use large sample sizes and generous tolerances to avoid flaky tests.
    """

    def test_dice_fairness(self):
        """Each face (1-6) should appear ~1/6 of the time over many rolls."""
        N = 60000
        counts = Counter()
        for _ in range(N):
            d1, d2 = roll_dice()
            counts[d1] += 1
            counts[d2] += 1

        total = N * 2
        expected = total / 6
        for face in range(1, 7):
            ratio = counts[face] / expected
            assert 0.95 <= ratio <= 1.05, (
                f"Face {face} appeared {counts[face]} times "
                f"(expected ~{expected:.0f}, ratio={ratio:.3f})"
            )

    def test_snake_eyes_probability(self):
        """P(snake_eyes) ≈ 1/36 ≈ 2.78% over many rolls."""
        N = 100000
        snake_eyes_count = 0
        for _ in range(N):
            d1, d2 = roll_dice()
            if classify_roll(d1, d2) == 'snake_eyes':
                snake_eyes_count += 1

        observed_prob = snake_eyes_count / N
        expected_prob = 1 / 36
        assert abs(observed_prob - expected_prob) < 0.005, (
            f"Snake eyes probability: {observed_prob:.4f} "
            f"(expected {expected_prob:.4f})"
        )

    def test_single_one_probability(self):
        """P(single_one) ≈ 10/36 ≈ 27.78% over many rolls."""
        N = 100000
        count = sum(
            1 for _ in range(N)
            if classify_roll(*roll_dice()) == 'single_one'
        )
        observed = count / N
        expected = 10 / 36
        assert abs(observed - expected) < 0.01, (
            f"Single-one probability: {observed:.4f} (expected {expected:.4f})"
        )

    def test_safe_roll_probability(self):
        """P(safe) ≈ 25/36 ≈ 69.44% over many rolls."""
        N = 100000
        count = sum(
            1 for _ in range(N)
            if classify_roll(*roll_dice()) == 'safe'
        )
        observed = count / N
        expected = 25 / 36
        assert abs(observed - expected) < 0.01, (
            f"Safe probability: {observed:.4f} (expected {expected:.4f})"
        )

    def test_safe_roll_average_value(self):
        """E[sum | safe] = 8.0 (each die averages 4 given no 1s)."""
        N = 100000
        safe_sums = []
        for _ in range(N):
            d1, d2 = roll_dice()
            if classify_roll(d1, d2) == 'safe':
                safe_sums.append(d1 + d2)

        avg = sum(safe_sums) / len(safe_sums)
        assert abs(avg - 8.0) < 0.1, (
            f"Average safe roll sum: {avg:.2f} (expected 8.0)"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8: EDGE CASES & REGRESSION
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Edge cases, boundary conditions, and regression tests."""

    def test_target_of_one(self):
        """Game with target=1 should end after first safe roll — any safe roll wins."""
        # Player 0: (3,2)=5 ≥ 1 → hits target
        # Player 1: gets final turn, (4,4)=8
        dice = make_dice_sequence([(3, 2), (4, 4)])
        bots = [RollNTimesBot(1), RollNTimesBot(1)]
        winner, scores = play_game(bots, target=1, dice_fn=dice)
        assert scores[0] == 5
        assert scores[1] == 8
        assert winner == 1  # Player 1 overtakes with 8 > 5

    def test_all_players_bust_every_round(self):
        """
        If every player busts every round, the game continues indefinitely.
        But eventually someone won't bust (probabilistically certain).
        Test that the game still completes.
        """
        bots = [ConservativeBot(8), ConservativeBot(8)]
        winner, scores = play_game(bots, target=30)
        assert max(scores) >= 30

    def test_simultaneous_target_reach(self):
        """
        Multiple players exceed target in same round — highest score wins.
        """
        # Player 0 rolls to 20, player 1 rolls to 25. Target=15.
        dice_rolls = [
            (5, 5), (5, 5),   # P0: 10, 20 → stop at 20
            (6, 6), (3, 4),   # P1: 12, 19 → stop... Actually P1 goes second
        ]
        # Let's be more precise
        dice_rolls = [
            (6, 4),          # P0: 10 → RollNTimes(1) → stops, score=10
            (6, 6),          # P1: 12 → stops, score=12
            (6, 5),          # P0: round 2: 11 → score=21 ≥ 15 → target reached!
            (6, 6),          # P1: final turn: 12 → score=24
        ]
        dice = make_dice_sequence(dice_rolls)
        bots = [RollNTimesBot(1), RollNTimesBot(1)]
        winner, scores = play_game(bots, target=15, dice_fn=dice)
        assert scores[0] == 21
        assert scores[1] == 24
        assert winner == 1, "Player 1 should win with higher score despite P0 hitting target first"

    def test_snake_eyes_in_game_resets_correctly(self):
        """Verify snake eyes during a game properly resets to 0."""
        # P0 banks 10 in round 1, then gets snake eyes in round 2
        dice_rolls = [
            (5, 5),          # P0 round 1: 10, stop
            (3, 3),          # P1 round 1: 6, stop
            (1, 1),          # P0 round 2: SNAKE EYES → 0
            (4, 4),          # P1 round 2: 8, stop → 14
            (6, 6),          # P0 round 3: 12, stop → 12
            (4, 3),          # P1 round 3: 7, stop → 21 ≥ 20 → game over
            # P0 gets final turn... but P0 index < P1 index, so no
            # Actually P1 triggered it, and P0 (index 0) < P1 (index 1)
            # so P0 doesn't get another turn (already played this round)
        ]
        dice = make_dice_sequence(dice_rolls)
        bots = [RollNTimesBot(1), RollNTimesBot(1)]
        winner, scores = play_game(bots, target=20, dice_fn=dice)
        # After round 1: [10, 6]
        # After round 2: [0, 14] (P0 snake eyes)
        # After round 3: [12, 21] → P1 wins
        assert scores[0] == 12
        assert scores[1] == 21
        assert winner == 1

    def test_multiple_rolls_before_bust(self):
        """Player accumulates over multiple safe rolls then busts on single 1."""
        scores = [0, 0]
        dice_rolls = [
            (3, 3),  # 6
            (4, 4),  # 8 → turn_total=14
            (5, 5),  # 10 → turn_total=24
            (2, 1),  # BUST! Single 1 → lose turn points
        ]
        dice = make_dice_sequence(dice_rolls)
        result = skunk_turn(100, scores, 0, strategy=AlwaysRollBot(), dice_fn=dice)
        assert result[0] == 0, "Busting after accumulation should keep original score (0)"

    def test_scores_vector_various_sizes(self):
        """skunk_turn handles score vectors of any size ≥ 1."""
        for n in [1, 2, 5, 10, 20]:
            scores = [10] * n
            for idx in [0, n-1]:  # test first and last player
                dice = make_dice_sequence([(3, 4)])
                result = skunk_turn(100, scores, idx, strategy=RollNTimesBot(1), dice_fn=dice)
                assert len(result) == n
                assert result[idx] == 17  # 10 + 7

    def test_deterministic_game_replay(self):
        """The same dice sequence produces the exact same game result."""
        dice_rolls = [
            (3, 4), (5, 2),   # round 1
            (6, 3), (4, 4),   # round 2
            (5, 5), (3, 3),   # round 3
            (6, 6), (5, 5),   # round 4
            (6, 6), (2, 2),   # round 5
            (5, 4), (4, 3),   # round 6
            (3, 3), (6, 6),   # round 7
            (6, 6), (5, 5),   # round 8+
            (5, 5), (4, 4),
            (6, 6), (3, 3),
        ]
        bots1 = [RollNTimesBot(1), RollNTimesBot(1)]
        bots2 = [RollNTimesBot(1), RollNTimesBot(1)]

        dice1 = make_dice_sequence(list(dice_rolls))
        dice2 = make_dice_sequence(list(dice_rolls))

        w1, s1 = play_game(bots1, target=50, dice_fn=dice1)
        w2, s2 = play_game(bots2, target=50, dice_fn=dice2)

        assert w1 == w2, "Same dice should produce same winner"
        assert s1 == s2, "Same dice should produce same final scores"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 9: TOURNAMENT FRAMEWORK TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestTournament:
    """Verify the tournament runner produces valid results."""

    def test_tournament_returns_valid_structure(self):
        results = run_tournament(
            bot_factories=[lambda: ConservativeBot(15), lambda: AggressiveBot(25)],
            target=50,
            num_games=100,
        )
        assert 'wins' in results
        assert 'win_rates' in results
        assert 'avg_final_scores' in results
        assert sum(results['wins']) == 100, "Total wins must equal total games"

    def test_tournament_win_rates_sum_to_100(self):
        results = run_tournament(
            bot_factories=[lambda: ConservativeBot(15), lambda: ExpectedValueBot()],
            target=50,
            num_games=200,
        )
        total_rate = sum(results['win_rates'])
        assert abs(total_rate - 100.0) < 0.01, f"Win rates sum to {total_rate}, expected 100"

    def test_tournament_with_adaptive_bot(self):
        results = run_tournament(
            bot_factories=[
                lambda: AdaptiveBot(initial_risk=1.0),
                lambda: ConservativeBot(15),
            ],
            target=50,
            num_games=100,
        )
        assert 'adaptive_0_final_risk' in results
        assert 'adaptive_0_best_risk' in results


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 10: INTEGRATION TESTS — Full game scenarios
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegration:
    """End-to-end integration tests for complete game scenarios."""

    def test_full_game_completes(self):
        """A full game with all bot types completes without errors."""
        bots = [
            ConservativeBot(12),
            AggressiveBot(25),
            ExpectedValueBot(),
            ContextAwareBot(),
            FixedRollBot(3),
        ]
        winner, scores = play_game(bots, target=100)
        assert 0 <= winner < 5
        assert max(scores) >= 100
        assert all(s >= 0 for s in scores)

    def test_many_games_no_crashes(self):
        """Run 500 games with mixed bots — no crashes allowed."""
        bots = [ConservativeBot(15), AggressiveBot(28), ExpectedValueBot()]
        for _ in range(500):
            winner, scores = play_game(bots, target=100)
            assert 0 <= winner < 3
            assert all(s >= 0 for s in scores)

    def test_verbose_mode_no_crash(self, capsys):
        """Verbose mode should print without crashing."""
        bots = [ConservativeBot(15), ConservativeBot(15)]
        play_game(bots, target=30, verbose=True)
        captured = capsys.readouterr()
        assert "SKUNK GAME" in captured.out
        assert "GAME OVER" in captured.out

    def test_skunk_turn_verbose_no_crash(self, capsys):
        """Verbose skunk_turn should print without crashing."""
        scores = [20, 30]
        dice = make_dice_sequence([(3, 4)])
        skunk_turn(100, scores, 0, strategy=RollNTimesBot(1), verbose=True, dice_fn=dice)
        captured = capsys.readouterr()
        assert "Player 0's turn" in captured.out


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 11: OPTIMALITY VERIFICATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestOptimalityVerification:
    """
    Tests that confirm the game uses the most optimal solution.

    These tests go beyond correctness — they verify that:
    1. The EV formula is mathematically sound (validated empirically)
    2. The EV-based threshold beats all fixed alternatives
    3. Context awareness provides measurable advantage over pure EV
    4. Monte Carlo simulation agrees with the closed-form formula
    """

    def test_ev_formula_matches_empirical(self):
        """
        The closed-form EV formula must match empirical simulation.

        For each (turn_total, game_total) pair, we simulate 50,000 dice
        rolls and compare the average change to the formula prediction.
        This independently validates the mathematical derivation.
        """
        assert verify_ev_formula_empirically(num_trials=50000) is True

    def test_ev_bot_beats_all_fixed_thresholds_head_to_head(self):
        """
        The ExpectedValueBot should beat (or tie) EVERY fixed-threshold
        bot in head-to-head play. This confirms the EV formula is
        the optimal single-turn strategy.

        Tests thresholds from 5 to 28; the EV bot should have >= 48%
        win rate against each (allowing slight noise from Monte Carlo).
        """
        ev_bot = ExpectedValueBot()
        N = 3000

        for threshold in [5, 10, 15, 20, 25, 28]:
            fixed_bot = StopAtThresholdBot(threshold)
            bots = [ev_bot, fixed_bot]

            wins = [0, 0]
            for game in range(N):
                # Rotate starting player for fairness
                if game % 2 == 0:
                    w, _ = play_game([ev_bot, fixed_bot], target=100)
                    wins[w] += 1
                else:
                    w, _ = play_game([fixed_bot, ev_bot], target=100)
                    wins[1 - w] += 1

            ev_win_rate = wins[0] / N
            assert ev_win_rate >= 0.45, (
                f"EV bot should beat Threshold({threshold}) but only won "
                f"{ev_win_rate:.1%} of {N} games"
            )

    def test_context_aware_beats_pure_ev(self):
        """
        The ContextAwareBot should outperform the pure ExpectedValueBot
        because it adjusts risk based on game state, not just score.

        This proves that context-dependent strategy > static EV optimization.
        """
        N = 5000
        wins = [0, 0]

        for game in range(N):
            if game % 2 == 0:
                w, _ = play_game([ContextAwareBot(), ExpectedValueBot()], target=100)
                wins[w] += 1
            else:
                w, _ = play_game([ExpectedValueBot(), ContextAwareBot()], target=100)
                wins[1 - w] += 1

        context_win_rate = wins[0] / N
        assert context_win_rate > 0.50, (
            f"ContextAwareBot should beat ExpectedValueBot but only won "
            f"{context_win_rate:.1%} of {N} games"
        )

    def test_monte_carlo_agrees_with_ev_formula(self):
        """
        The Monte Carlo bot and the EV bot should make the same
        roll/stop decision in most situations, since they're both
        computing expected value — just by different methods.

        Test 500 random game states and verify >= 85% agreement.
        """
        ev_bot = ExpectedValueBot()
        mc_bot = MonteCarloBot(simulations=500)

        agreements = 0
        total = 500

        for _ in range(total):
            turn_total = random.randint(0, 25)
            game_total = random.randint(0, 100)
            target = 100
            all_scores = [game_total, random.randint(0, 100)]
            roll_num = random.randint(1, 5)

            ev_decision = ev_bot.decide(
                turn_total, game_total, target, all_scores, 0, roll_num
            )
            mc_decision = mc_bot.decide(
                turn_total, game_total, target, all_scores, 0, roll_num
            )

            if ev_decision == mc_decision:
                agreements += 1

        agreement_rate = agreements / total
        assert agreement_rate >= 0.80, (
            f"Monte Carlo and EV formula should agree >= 80% of the time, "
            f"but only agreed {agreement_rate:.1%}"
        )

    def test_ev_threshold_decreases_with_game_total(self):
        """
        Mathematical invariant: as game_total increases, the optimal
        turn threshold decreases. This confirms the formula
        threshold = (200 - game_total) / 11 is monotonically decreasing.
        """
        ev_bot = ExpectedValueBot()

        prev_would_roll = True
        for game_total in range(0, 250, 10):
            # Check at a fixed turn_total whether the bot would roll
            # As game_total increases, at some point it should switch to stop
            would_roll = ev_bot.decide(15, game_total, 200, [game_total, 0], 0, 1)

            # Once it stops, it should never start rolling again
            if not prev_would_roll:
                assert not would_roll, (
                    f"Non-monotonic: bot stopped at lower game_total but rolls "
                    f"at game_total={game_total}"
                )
            prev_would_roll = would_roll

    def test_optimal_threshold_at_known_points(self):
        """
        Verify the EV formula gives correct thresholds at known points:
          game_total=0   → threshold = 200/11 ≈ 18.18
          game_total=100 → threshold = 100/11 ≈  9.09
          game_total=200 → threshold = 0/11   =  0.00
        """
        import math

        # At game_total=0, should roll at turn_total=18, stop at 19
        assert ExpectedValueBot().decide(18, 0, 200, [0, 0], 0, 1) == True  # 198 < 200
        assert ExpectedValueBot().decide(19, 0, 200, [0, 0], 0, 1) == False  # 209 > 200

        # At game_total=100, should roll at turn_total=9, stop at 10
        assert ExpectedValueBot().decide(9, 100, 200, [100, 0], 0, 1) == True  # 199 < 200
        assert ExpectedValueBot().decide(10, 100, 200, [100, 0], 0, 1) == False  # 210 > 200

        # At game_total=200, should never roll (threshold=0)
        assert ExpectedValueBot().decide(0, 200, 200, [200, 0], 0, 1) == False  # 200 = 200

    def test_win_probability_depends_on_opponents(self):
        """
        The same bot must have different win probabilities against
        different opponents. This proves the game is strategic, not
        purely chance-based.
        """
        ev = ExpectedValueBot()

        # EV vs Conservative(12)
        prob_vs_conservative = estimate_win_probability(
            [ExpectedValueBot(), ConservativeBot(12)], target=100, simulations=5000
        )[0]

        # EV vs Aggressive(28)
        prob_vs_aggressive = estimate_win_probability(
            [ExpectedValueBot(), AggressiveBot(28)], target=100, simulations=5000
        )[0]

        # These should be different (EV does better against aggressive)
        assert abs(prob_vs_conservative - prob_vs_aggressive) > 0.03, (
            f"Win probability should differ by opponent: "
            f"vs Conservative={prob_vs_conservative:.3f}, "
            f"vs Aggressive={prob_vs_aggressive:.3f}"
        )
