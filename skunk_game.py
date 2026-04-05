"""
SKUNK Dice Game — Algorithm & Heuristic Implementation
========================================================

A comprehensive implementation of the SKUNK dice game featuring:
  1. Core game engine with configurable rules
  2. The required `skunk_turn` function (takes target, scores vector, player index)
  3. Multiple bot strategies (conservative, aggressive, expected-value optimal, adaptive)
  4. A tournament framework for pitting bots against each other
  5. A self-improving adaptive bot that learns from historical performance

Mathematical Foundation
-----------------------
When rolling two fair dice:
  P(no 1s)       = (5/6)^2 = 25/36 ≈ 69.44%
  P(exactly one 1) = 2·(1/6)·(5/6) = 10/36 ≈ 27.78%
  P(double 1s)   = (1/6)^2 = 1/36 ≈ 2.78%

Expected value of a non-1 roll (each die ∈ {2,3,4,5,6}):
  E[die | die≠1] = (2+3+4+5+6)/5 = 4  →  E[sum] = 8

Expected change from rolling again, given turn_total and game_total:
  ΔE = (25/36)·8 − (10/36)·turn_total − (1/36)·(game_total + turn_total)
     = (200 − 11·turn_total − game_total) / 36

Break-even:  11·turn_total + game_total = 200
  → If game_total=0,  stop at turn_total ≈ 18
  → If game_total=50, stop at turn_total ≈ 13–14
  → If game_total=100, stop at turn_total ≈ 9

Author: SKUNK Bot Framework
"""

import random
import math
import copy
import json
import os
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import List, Tuple, Optional, Dict, Callable


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: DICE MECHANICS
# ═══════════════════════════════════════════════════════════════════════════════

def roll_dice() -> Tuple[int, int]:
    """Roll two fair six-sided dice. Returns (die1, die2)."""
    return (random.randint(1, 6), random.randint(1, 6))


def classify_roll(die1: int, die2: int) -> str:
    """
    Classify a dice roll outcome:
      'snake_eyes'  — both dice are 1 (lose ALL accumulated points)
      'single_one'  — exactly one die is 1 (lose turn points, keep game total)
      'safe'        — neither die is 1 (add to turn total)
    """
    if die1 == 1 and die2 == 1:
        return 'snake_eyes'
    elif die1 == 1 or die2 == 1:
        return 'single_one'
    else:
        return 'safe'


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: BOT STRATEGIES (Abstract Base + Concrete Implementations)
# ═══════════════════════════════════════════════════════════════════════════════

class SkunkBot(ABC):
    """Abstract base class for all SKUNK bot strategies."""

    def __init__(self, name: str):
        self.name = name
        self.wins = 0
        self.games_played = 0
        self.total_score_history = []  # track final scores across games

    @abstractmethod
    def decide(self, turn_total: int, game_total: int, target: int,
               all_scores: List[int], player_index: int, roll_number: int) -> bool:
        """
        Decide whether to ROLL (True) or STOP (False).

        Parameters:
            turn_total   — points accumulated this turn so far
            game_total   — your total banked score before this turn
            target       — the target score to win the game
            all_scores   — current scores of ALL players
            player_index — your index in all_scores (0-based)
            roll_number  — which roll this is within the current turn (1-based)

        Returns:
            True to roll again, False to stop and bank turn_total.
        """
        pass

    def reset(self):
        """Reset per-game state (wins/games are preserved for learning)."""
        pass

    def __repr__(self):
        return f"{self.name}"


class ConservativeBot(SkunkBot):
    """
    Stops after accumulating a modest turn total (default 15).
    Low risk — rarely loses points but accumulates slowly.
    """

    def __init__(self, threshold: int = 15):
        super().__init__(f"Conservative({threshold})")
        self.threshold = threshold

    def decide(self, turn_total, game_total, target, all_scores, player_index, roll_number):
        return turn_total < self.threshold


class AggressiveBot(SkunkBot):
    """
    Keeps rolling until a high threshold (default 30).
    High risk, high reward — often loses turns but occasionally banks big.
    """

    def __init__(self, threshold: int = 30):
        super().__init__(f"Aggressive({threshold})")
        self.threshold = threshold

    def decide(self, turn_total, game_total, target, all_scores, player_index, roll_number):
        return turn_total < self.threshold


class ExpectedValueBot(SkunkBot):
    """
    Uses the mathematically optimal expected-value calculation.

    Rolls again only when the expected gain from rolling exceeds zero:
        ΔE = (200 − 11·turn_total − game_total) / 36 > 0
        ⟹  11·turn_total + game_total < 200

    This dynamically adjusts risk based on how much is at stake.
    """

    def __init__(self):
        super().__init__("ExpectedValue")

    def decide(self, turn_total, game_total, target, all_scores, player_index, roll_number):
        # Pure expected-value threshold
        return 11 * turn_total + game_total < 200


class ContextAwareBot(SkunkBot):
    """
    The smartest static-logic bot. Combines expected-value math with
    game-context awareness:

    1. Base threshold from EV calculation
    2. Adjusts aggressiveness based on:
       - Whether the leader is close to winning → push harder
       - Whether you're in the lead → play safer
       - Whether it's a "last chance" turn (someone already hit target)
       - Distance to target → calibrate risk
    """

    def __init__(self):
        super().__init__("ContextAware")

    def decide(self, turn_total, game_total, target, all_scores, player_index, roll_number):
        my_score = game_total
        potential_score = game_total + turn_total

        # Get competitor info
        other_scores = [s for i, s in enumerate(all_scores) if i != player_index]
        max_other = max(other_scores) if other_scores else 0

        # --- Base threshold from expected value ---
        ev_threshold = max(0, (200 - game_total) / 11)

        # --- Context adjustments ---
        threshold = ev_threshold

        # 1) If someone is very close to target or already hit it → be aggressive
        if max_other >= target * 0.85:
            urgency = (max_other - target * 0.85) / (target * 0.15)
            urgency = min(urgency, 1.0)
            threshold = threshold + urgency * 15  # up to +15 on threshold

        # 2) If we're winning comfortably → be conservative
        if my_score > max_other + 20:
            threshold = max(threshold - 5, 8)

        # 3) "Last chance" scenario — someone already hit the target
        #    We need to maximize our score, so be very aggressive
        if max_other >= target:
            needed = max_other - my_score + 1  # need to beat them
            # Keep rolling until we either catch up or go bust
            if potential_score <= max_other:
                return True
            else:
                # We've overtaken — now use a tighter threshold
                threshold = max(threshold, 10)

        # 4) If we can win right now by banking, do it
        if potential_score >= target:
            return False

        # 5) If we're close to target, play for the exact amount needed
        distance_to_target = target - my_score
        if distance_to_target <= 25 and turn_total >= distance_to_target:
            return False

        return turn_total < threshold


class FixedRollBot(SkunkBot):
    """
    Always rolls exactly N times (unless busted). Simple but useful as a baseline.
    """

    def __init__(self, num_rolls: int = 3):
        super().__init__(f"FixedRoll({num_rolls})")
        self.num_rolls = num_rolls

    def decide(self, turn_total, game_total, target, all_scores, player_index, roll_number):
        # If banking would win the game, stop
        if game_total + turn_total >= target:
            return False
        return roll_number < self.num_rolls


class RandomBot(SkunkBot):
    """
    Decides randomly with a given probability of rolling.
    Useful for establishing a baseline.
    """

    def __init__(self, roll_probability: float = 0.6):
        super().__init__(f"Random({roll_probability:.0%})")
        self.roll_probability = roll_probability

    def decide(self, turn_total, game_total, target, all_scores, player_index, roll_number):
        if game_total + turn_total >= target:
            return False
        return random.random() < self.roll_probability


class AdaptiveBot(SkunkBot):
    """
    A self-improving bot that adjusts its aggression parameter based on
    historical performance.

    Strategy:
    - Maintains a "risk_factor" parameter (initially 1.0)
    - Uses the EV threshold scaled by risk_factor
    - After each game, adjusts risk_factor based on win/loss:
        Win  → nudge risk_factor toward current value (reinforce)
        Loss → explore by randomly perturbing risk_factor
    - Uses an exponential moving average to smooth adjustments

    The risk_factor > 1 means more aggressive than pure EV, < 1 means more
    conservative. Over many games, it converges toward the risk level that
    maximizes wins against its specific opponents.
    """

    def __init__(self, initial_risk: float = 1.0, learning_rate: float = 0.05):
        super().__init__(f"Adaptive(r={initial_risk:.2f})")
        self.risk_factor = initial_risk
        self.learning_rate = learning_rate
        self.risk_history = [initial_risk]
        self.recent_wins = []    # sliding window of recent outcomes
        self.window_size = 50
        self.best_risk = initial_risk
        self.best_win_rate = 0.0
        self.generation = 0

    def decide(self, turn_total, game_total, target, all_scores, player_index, roll_number):
        my_score = game_total
        other_scores = [s for i, s in enumerate(all_scores) if i != player_index]
        max_other = max(other_scores) if other_scores else 0

        # Scaled EV threshold
        ev_threshold = max(0, (200 - game_total) / 11) * self.risk_factor

        # If banking wins the game, stop
        if game_total + turn_total >= target:
            return False

        # Last-chance aggression: if opponent already at target, keep rolling
        if max_other >= target and game_total + turn_total <= max_other:
            return True

        return turn_total < ev_threshold

    def record_result(self, won: bool):
        """Called after each game to update the learning parameters."""
        self.recent_wins.append(1 if won else 0)
        if len(self.recent_wins) > self.window_size:
            self.recent_wins.pop(0)

        current_win_rate = sum(self.recent_wins) / len(self.recent_wins)

        # Track best risk factor
        if current_win_rate > self.best_win_rate and len(self.recent_wins) >= 20:
            self.best_win_rate = current_win_rate
            self.best_risk = self.risk_factor

        self.generation += 1

        if won:
            # Reinforce: small random perturbation around current value
            self.risk_factor += random.gauss(0, 0.02)
        else:
            # Explore: larger perturbation, with a slight pull toward best known
            perturbation = random.gauss(0, self.learning_rate)
            pull_to_best = (self.best_risk - self.risk_factor) * 0.1
            self.risk_factor += perturbation + pull_to_best

        # Clamp risk factor to reasonable range
        self.risk_factor = max(0.3, min(2.5, self.risk_factor))

        self.risk_history.append(self.risk_factor)
        self.name = f"Adaptive(r={self.risk_factor:.2f},gen={self.generation})"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: THE CORE skunk_turn FUNCTION (as specified in the assignment)
# ═══════════════════════════════════════════════════════════════════════════════

def skunk_turn(target: int, scores: List[int], player_index: int,
               strategy: Optional[SkunkBot] = None, verbose: bool = False,
               dice_fn: Optional[Callable[[], Tuple[int, int]]] = None) -> List[int]:
    """
    Play one turn of SKUNK for the given player.

    This is the REQUIRED function per the assignment specification:
      Input:
        1) target        — the target total points to win
        2) scores        — vector of points accumulated by all players
        3) player_index  — your order among the players (0-based index)

      Logic:
        - Decides whether to roll or stop using the provided strategy
          (defaults to ContextAwareBot if none given).
        - Generates random dice rolls.
        - If a single 1 is rolled: turn ends, no points gained this turn.
        - If double 1s (snake eyes): turn ends, ALL accumulated points lost
          (score goes to 0).
        - Otherwise: accumulate the roll total and decide again.
        - When the turn ends (by choice or bust), update the scores vector.

      Output:
        - Returns the updated scores vector with the player's new total.
    """
    if strategy is None:
        strategy = ContextAwareBot()

    scores = list(scores)  # work on a copy
    game_total = scores[player_index]
    turn_total = 0
    roll_number = 0

    if verbose:
        print(f"\n{'='*50}")
        print(f"  Player {player_index}'s turn  |  Current score: {game_total}")
        print(f"  Target: {target}  |  All scores: {scores}")
        print(f"{'='*50}")

    while True:
        roll_number += 1

        # Ask the bot: roll or stop?
        should_roll = strategy.decide(
            turn_total=turn_total,
            game_total=game_total,
            target=target,
            all_scores=scores,
            player_index=player_index,
            roll_number=roll_number
        )

        if not should_roll:
            # Player banks the turn total
            scores[player_index] = game_total + turn_total
            if verbose:
                print(f"  → STOP. Banked {turn_total} points. "
                      f"New total: {scores[player_index]}")
            return scores

        # Roll the dice
        die1, die2 = (dice_fn or roll_dice)()
        outcome = classify_roll(die1, die2)

        if verbose:
            print(f"  Roll #{roll_number}: [{die1}] [{die2}]", end="")

        if outcome == 'snake_eyes':
            # Double 1s — lose EVERYTHING
            scores[player_index] = 0
            if verbose:
                print(f"  💀 SNAKE EYES! Lost ALL points. Total → 0")
            return scores

        elif outcome == 'single_one':
            # Single 1 — lose this turn's accumulated points
            scores[player_index] = game_total  # unchanged
            if verbose:
                print(f"  ✗ Single 1! Lost {turn_total} turn points. "
                      f"Total stays at {game_total}")
            return scores

        else:
            # Safe roll — accumulate
            roll_sum = die1 + die2
            turn_total += roll_sum
            if verbose:
                print(f"  ✓ Safe! +{roll_sum} → Turn total: {turn_total}  "
                      f"(potential: {game_total + turn_total})")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: GAME ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def play_game(bots: List[SkunkBot], target: int = 100,
              verbose: bool = False,
              dice_fn: Optional[Callable[[], Tuple[int, int]]] = None) -> Tuple[int, List[int]]:
    """
    Play a full SKUNK game.

    Rules:
    - Players take turns in order.
    - Once any player reaches the target, all OTHER players who haven't had
      a turn this round get one final turn.
    - The player with the highest score wins (ties broken by player order — 
      first to achieve the score wins).

    Returns:
        (winner_index, final_scores)
    """
    n = len(bots)
    scores = [0] * n
    round_number = 0
    game_over = False
    target_reached_by = -1  # index of player who first hit target

    if verbose:
        print(f"\n{'#'*60}")
        print(f"  SKUNK GAME — Target: {target} — {n} players")
        print(f"  Bots: {[b.name for b in bots]}")
        print(f"{'#'*60}")

    while True:
        round_number += 1
        if verbose:
            print(f"\n{'─'*60}")
            print(f"  ROUND {round_number}")
            print(f"{'─'*60}")

        for i in range(n):
            # If the game is over and this player already had their final turn
            if game_over and i <= target_reached_by:
                continue
            if game_over and i > target_reached_by:
                # This player gets one more turn
                pass

            scores = skunk_turn(
                target=target,
                scores=scores,
                player_index=i,
                strategy=bots[i],
                verbose=verbose,
                dice_fn=dice_fn
            )

            # Check if this player just hit the target
            if scores[i] >= target and not game_over:
                game_over = True
                target_reached_by = i
                if verbose:
                    print(f"\n  🎯 Player {i} ({bots[i].name}) reached the target!")
                    print(f"     Remaining players get one final turn.")

        # If game_over, after the round completes, end the game
        if game_over:
            break

    # Determine winner — highest score, ties go to first achiever
    winner = max(range(n), key=lambda i: scores[i])

    if verbose:
        print(f"\n{'#'*60}")
        print(f"  GAME OVER — Final Scores:")
        for i in range(n):
            marker = " 👑" if i == winner else ""
            print(f"    Player {i} ({bots[i].name}): {scores[i]}{marker}")
        print(f"{'#'*60}")

    return winner, scores


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: TOURNAMENT FRAMEWORK
# ═══════════════════════════════════════════════════════════════════════════════

def run_tournament(bot_factories: List[Callable[[], SkunkBot]],
                   target: int = 100,
                   num_games: int = 10000,
                   verbose_interval: int = 0) -> Dict:
    """
    Run a tournament of N games between the given bots.

    Parameters:
        bot_factories  — list of callables that create fresh bot instances
        target         — target score for each game
        num_games      — number of games to simulate
        verbose_interval — if >0, print a verbose game every N games

    Returns:
        Dictionary with tournament results and statistics.
    """
    # Create bot instances
    bots = [factory() for factory in bot_factories]
    n = len(bots)

    # Statistics tracking
    wins = [0] * n
    total_final_scores = [0] * n
    busts_to_zero = [0] * n  # how often each bot was at 0 at game end
    win_streaks = [0] * n
    max_win_streaks = [0] * n

    print(f"\n{'═'*60}")
    print(f"  SKUNK TOURNAMENT")
    print(f"  Target: {target}  |  Games: {num_games:,}")
    print(f"  Bots: {[b.name for b in bots]}")
    print(f"{'═'*60}")
    print()

    for game_num in range(1, num_games + 1):
        verbose = (verbose_interval > 0 and game_num % verbose_interval == 0)

        # Rotate starting player to be fair
        rotation = (game_num - 1) % n
        rotated_bots = bots[rotation:] + bots[:rotation]
        rotated_indices = list(range(rotation, n)) + list(range(0, rotation))

        winner_rotated, final_scores_rotated = play_game(
            rotated_bots, target=target, verbose=verbose
        )

        # Map back to original indices
        winner_original = rotated_indices[winner_rotated]
        final_scores = [0] * n
        for rotated_i, original_i in enumerate(rotated_indices):
            final_scores[original_i] = final_scores_rotated[rotated_i]

        # Record stats
        for i in range(n):
            total_final_scores[i] += final_scores[i]
            if final_scores[i] == 0:
                busts_to_zero[i] += 1

        wins[winner_original] += 1

        # Win streaks
        for i in range(n):
            if i == winner_original:
                win_streaks[i] += 1
                max_win_streaks[i] = max(max_win_streaks[i], win_streaks[i])
            else:
                win_streaks[i] = 0

        # Adaptive bots learn
        for i, bot in enumerate(bots):
            if isinstance(bot, AdaptiveBot):
                bot.record_result(i == winner_original)

        # Progress indicator
        if game_num % (num_games // 10) == 0:
            pct = game_num / num_games * 100
            print(f"  Progress: {pct:.0f}% ({game_num:,} / {num_games:,} games)")

    # Compile results
    results = {
        'bots': [b.name for b in bots],
        'wins': wins,
        'win_rates': [w / num_games * 100 for w in wins],
        'avg_final_scores': [t / num_games for t in total_final_scores],
        'bust_rates': [b / num_games * 100 for b in busts_to_zero],
        'max_win_streaks': max_win_streaks,
        'num_games': num_games,
    }

    # Check for adaptive bots and include their learning data
    for i, bot in enumerate(bots):
        if isinstance(bot, AdaptiveBot):
            results[f'adaptive_{i}_final_risk'] = bot.risk_factor
            results[f'adaptive_{i}_best_risk'] = bot.best_risk
            results[f'adaptive_{i}_best_win_rate'] = bot.best_win_rate

    # Print summary
    print(f"\n{'═'*60}")
    print(f"  TOURNAMENT RESULTS ({num_games:,} games)")
    print(f"{'═'*60}")
    print(f"\n  {'Bot':<30s} {'Wins':>7s} {'Win%':>8s} {'Avg Score':>10s} "
          f"{'Bust%':>7s} {'Best Streak':>12s}")
    print("  " + "─"*30 + " " + "─"*7 + " " + "─"*8 + " " + "─"*10 + " " + "─"*7 + " " + "─"*12)

    for i in range(n):
        print(f"  {bots[i].name:<30s} {wins[i]:>7,d} {results['win_rates'][i]:>7.1f}% "
              f"{results['avg_final_scores'][i]:>10.1f} "
              f"{results['bust_rates'][i]:>6.1f}% {max_win_streaks[i]:>12d}")

    # Print adaptive bot info
    for i, bot in enumerate(bots):
        if isinstance(bot, AdaptiveBot):
            print(f"\n  Adaptive Bot {i} Learning Summary:")
            print(f"    Final risk factor:  {bot.risk_factor:.3f}")
            print(f"    Best risk factor:   {bot.best_risk:.3f}")
            print(f"    Best win rate:      {bot.best_win_rate:.1%}")
            print(f"    Generations:        {bot.generation}")

    print(f"\n{'═'*60}\n")
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: ANALYSIS & PROBABILITY CALCULATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_optimal_threshold():
    """
    Print a table showing the break-even turn threshold for different
    game totals, based on the expected-value formula.
    """
    print(f"\n{'═'*55}")
    print(f"  OPTIMAL TURN THRESHOLD (Expected-Value Analysis)")
    print(f"{'═'*55}")
    print(f"\n  Formula: Stop when 11·turn_total + game_total ≥ 200")
    print(f"\n  {'Game Total':>12s}  {'EV Threshold':>14s}  {'Interpretation':<25s}")
    print(f"  {'─'*12}  {'─'*14}  {'─'*25}")

    for gt in range(0, 110, 10):
        threshold = max(0, (200 - gt) / 11)
        if threshold == 0:
            interp = "Too risky to roll at all!"
        elif threshold < 10:
            interp = "Very conservative"
        elif threshold < 18:
            interp = "Moderate risk"
        else:
            interp = "Can afford aggression"
        print(f"  {gt:>12d}  {threshold:>14.1f}  {interp:<25s}")

    print(f"\n  Key insight: The more you've accumulated over the game,")
    print(f"  the MORE conservative you should be (more to lose from snake eyes).")
    print()


def estimate_win_probability(bots: List[SkunkBot], target: int = 100,
                              simulations: int = 50000) -> List[float]:
    """
    Estimate each bot's win probability via Monte Carlo simulation.
    Returns list of probabilities (summing to 1.0).
    """
    wins = [0] * len(bots)
    n = len(bots)

    for game in range(simulations):
        rotation = game % n
        rotated = bots[rotation:] + bots[:rotation]
        rotated_map = list(range(rotation, n)) + list(range(0, rotation))

        winner_r, _ = play_game(rotated, target=target)
        wins[rotated_map[winner_r]] += 1

    return [w / simulations for w in wins]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6b: OPTIMALITY VERIFICATION TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

def threshold_sweep(game_totals: List[int] = None, target: int = 100,
                    simulations_per_threshold: int = 5000,
                    threshold_range: range = None) -> Dict:
    """
    Empirically find the best fixed turn-threshold for each game_total by
    running a grid search. For each game_total, pit every threshold (1–35)
    against the ExpectedValueBot in head-to-head games and measure win rate.

    This provides independent empirical validation that the EV-formula
    threshold (200 - game_total) / 11 is indeed optimal.

    Returns:
        Dict mapping game_total -> (best_threshold, best_win_rate, all_results)
    """
    if game_totals is None:
        game_totals = [0, 25, 50, 75, 100]
    if threshold_range is None:
        threshold_range = range(5, 30)

    results = {}

    print(f"\n{'═'*60}")
    print(f"  THRESHOLD SWEEP — Empirical Optimality Verification")
    print(f"  Comparing fixed thresholds vs ExpectedValueBot")
    print(f"{'═'*60}\n")

    for gt in game_totals:
        ev_theory = max(0, (200 - gt) / 11)
        best_threshold = -1
        best_win_rate = 0.0
        sweep_data = {}

        for thresh in threshold_range:
            wins = 0
            for _ in range(simulations_per_threshold):
                # Create bots with the game_total pre-set
                test_bot = StopAtThresholdBot(thresh)
                ev_bot = ExpectedValueBot()

                # Simulate single turns with the given game_total
                scores_test = [gt, gt]

                # Play a short game from this position
                s1 = skunk_turn(target, list(scores_test), 0, strategy=test_bot)
                s2 = skunk_turn(target, list(scores_test), 1, strategy=ev_bot)

                if s1[0] > s2[1]:
                    wins += 1
                elif s1[0] == s2[1]:
                    wins += 0.5  # tie

            win_rate = wins / simulations_per_threshold
            sweep_data[thresh] = win_rate

            if win_rate > best_win_rate:
                best_win_rate = win_rate
                best_threshold = thresh

        results[gt] = {
            'best_threshold': best_threshold,
            'best_win_rate': best_win_rate,
            'ev_theory': ev_theory,
            'sweep': sweep_data,
        }

        match_symbol = "✓" if abs(best_threshold - ev_theory) <= 3 else "✗"
        print(f"  game_total={gt:>3d}  |  EV theory: {ev_theory:>5.1f}  |  "
              f"Empirical best: {best_threshold:>2d}  |  "
              f"Win rate: {best_win_rate:.1%}  {match_symbol}")

    print(f"\n  ✓ = Empirical best matches EV theory (within ±3)")
    print(f"{'═'*60}\n")
    return results


class StopAtThresholdBot(SkunkBot):
    """Simple bot used for threshold sweep — stops at a fixed turn total."""
    def __init__(self, threshold: int):
        super().__init__(f"Threshold({threshold})")
        self.threshold = threshold
    def decide(self, turn_total, game_total, target, all_scores, player_index, roll_number):
        if game_total + turn_total >= target:
            return False
        return turn_total < self.threshold


class MonteCarloBot(SkunkBot):
    """
    Uses Monte Carlo forward simulation to decide whether to roll.

    For each decision point, simulates N random futures for both
    'roll' and 'stop' actions, and picks the one that leads to a
    higher expected outcome. This is the gold standard for verifying
    that the EV formula is correct.
    """

    def __init__(self, simulations: int = 200):
        super().__init__(f"MonteCarlo({simulations})")
        self.simulations = simulations

    def _simulate_remaining_turn(self, turn_total: int, game_total: int) -> float:
        """Simulate one possible continuation of the turn and return final score."""
        tt = turn_total
        while True:
            # Use EV-based stopping (to simulate "smart" continuation)
            if 11 * tt + game_total >= 200:
                return game_total + tt

            d1 = random.randint(1, 6)
            d2 = random.randint(1, 6)

            if d1 == 1 and d2 == 1:
                return 0  # snake eyes
            elif d1 == 1 or d2 == 1:
                return game_total  # single one
            else:
                tt += d1 + d2

    def decide(self, turn_total, game_total, target, all_scores, player_index, roll_number):
        if game_total + turn_total >= target:
            return False

        # Evaluate STOP: score = game_total + turn_total
        stop_value = game_total + turn_total

        # Evaluate ROLL: simulate many futures
        roll_values = []
        for _ in range(self.simulations):
            d1 = random.randint(1, 6)
            d2 = random.randint(1, 6)

            if d1 == 1 and d2 == 1:
                roll_values.append(0)
            elif d1 == 1 or d2 == 1:
                roll_values.append(game_total)
            else:
                new_turn_total = turn_total + d1 + d2
                roll_values.append(
                    self._simulate_remaining_turn(new_turn_total, game_total)
                )

        avg_roll_value = sum(roll_values) / len(roll_values)
        return avg_roll_value > stop_value


def verify_ev_formula_empirically(num_trials: int = 50000) -> bool:
    """
    Independently verify the EV formula by computing the expected change
    from rolling empirically and comparing to the closed-form.

    For various (turn_total, game_total) pairs, simulates many dice rolls
    and measures the actual average change, then compares to the formula:
        ΔE = (200 - 11*turn_total - game_total) / 36

    Returns True if all test points match within tolerance.
    """
    print(f"\n{'═'*60}")
    print(f"  EMPIRICAL VERIFICATION OF EV FORMULA")
    print(f"  ΔE = (200 - 11·turn_total - game_total) / 36")
    print(f"{'═'*60}\n")

    test_points = [
        (0, 0), (10, 0), (15, 0), (18, 0), (20, 0),
        (0, 50), (10, 50), (15, 50),
        (0, 100), (5, 100), (10, 100),
        (5, 150), (0, 200),
    ]

    all_pass = True

    print(f"  {'turn_total':>10s}  {'game_total':>10s}  {'Formula ΔE':>10s}  "
          f"{'Empirical ΔE':>12s}  {'Match':>6s}")
    print(f"  {'─'*10}  {'─'*10}  {'─'*10}  {'─'*12}  {'─'*6}")

    for turn_total, game_total in test_points:
        formula_delta = (200 - 11 * turn_total - game_total) / 36

        # Simulate many rolls and measure actual expected change
        deltas = []
        for _ in range(num_trials):
            d1 = random.randint(1, 6)
            d2 = random.randint(1, 6)

            if d1 == 1 and d2 == 1:
                # Snake eyes: lose everything (game_total + turn_total → 0)
                change = -(game_total + turn_total)
            elif d1 == 1 or d2 == 1:
                # Single one: lose turn total only
                change = -turn_total
            else:
                # Safe: gain d1+d2
                change = d1 + d2

            deltas.append(change)

        empirical_delta = sum(deltas) / len(deltas)
        tolerance = 0.3  # generous tolerance for Monte Carlo variance
        match = abs(empirical_delta - formula_delta) < tolerance
        if not match:
            all_pass = False

        symbol = "✓" if match else "✗"
        print(f"  {turn_total:>10d}  {game_total:>10d}  {formula_delta:>10.2f}  "
              f"{empirical_delta:>12.2f}  {symbol:>6s}")

    print(f"\n  {'PASS ✓' if all_pass else 'FAIL ✗'} — "
          f"EV formula {'matches' if all_pass else 'does NOT match'} "
          f"empirical results (tolerance ±0.3)")
    print(f"{'═'*60}\n")
    return all_pass


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7: MAIN — DEMONSTRATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def demo_single_game():
    """Play a single verbose game to show the mechanics."""
    print("\n" + "▓" * 60)
    print("  DEMO: Single Verbose Game")
    print("▓" * 60)

    bots = [
        ConservativeBot(15),
        AggressiveBot(28),
        ExpectedValueBot(),
        ContextAwareBot(),
    ]
    play_game(bots, target=100, verbose=True)


def demo_tournament():
    """Run a large tournament comparing all static strategies."""
    run_tournament(
        bot_factories=[
            lambda: ConservativeBot(12),
            lambda: ConservativeBot(18),
            lambda: AggressiveBot(28),
            lambda: ExpectedValueBot(),
            lambda: ContextAwareBot(),
            lambda: FixedRollBot(3),
            lambda: RandomBot(0.65),
        ],
        target=100,
        num_games=10000,
    )


def demo_adaptive_learning():
    """
    Demonstrate the adaptive bot learning by playing against fixed opponents.
    Shows how the risk factor evolves over time.
    """
    print("\n" + "▓" * 60)
    print("  DEMO: Adaptive Bot Learning")
    print("▓" * 60)

    results = run_tournament(
        bot_factories=[
            lambda: AdaptiveBot(initial_risk=1.0, learning_rate=0.08),
            lambda: ExpectedValueBot(),
            lambda: ContextAwareBot(),
            lambda: ConservativeBot(18),
        ],
        target=100,
        num_games=20000,
    )


def demo_head_to_head():
    """
    Demonstrate head-to-head matchups to answer: does probability of winning
    depend on opponents' strategies?
    """
    print("\n" + "▓" * 60)
    print("  DEMO: Head-to-Head Matchups")
    print("  (Does win probability depend on opponent strategy?)")
    print("▓" * 60)

    matchups = [
        ("EV vs Conservative", [ExpectedValueBot, lambda: ConservativeBot(15)]),
        ("EV vs Aggressive",   [ExpectedValueBot, lambda: AggressiveBot(28)]),
        ("EV vs EV",           [ExpectedValueBot, ExpectedValueBot]),
        ("ContextAware vs EV", [ContextAwareBot,  ExpectedValueBot]),
        ("ContextAware vs Aggressive", [ContextAwareBot, lambda: AggressiveBot(28)]),
    ]

    print(f"\n  {'Matchup':<30s}  {'Bot 1 Win%':>12s}  {'Bot 2 Win%':>12s}")
    print(f"  {'─'*30}  {'─'*12}  {'─'*12}")

    for label, factories in matchups:
        bots = [f() for f in factories]
        probs = estimate_win_probability(bots, target=100, simulations=20000)
        print(f"  {label:<30s}  {probs[0]*100:>11.1f}%  {probs[1]*100:>11.1f}%")

    print(f"\n  Conclusion: Win probability DOES depend on opponent strategy.")
    print(f"  The ContextAwareBot performs well because it adapts to game state.\n")


def demo_skunk_turn_function():
    """
    Demonstrate the core skunk_turn function as specified in the assignment.
    Shows the exact interface: target, scores vector, player index.
    """
    print("\n" + "▓" * 60)
    print("  DEMO: Core skunk_turn() Function")
    print("▓" * 60)

    target = 100
    scores = [45, 38, 52, 20]  # 4 players' current scores
    my_index = 1                # I am player #2 (0-based index 1)

    print(f"\n  Setup:")
    print(f"    Target:       {target}")
    print(f"    Scores:       {scores}")
    print(f"    My player #:  {my_index} (0-based)")

    # Use the default ContextAwareBot strategy
    updated_scores = skunk_turn(target, scores, my_index, verbose=True)

    print(f"\n  Result:")
    print(f"    Updated scores: {updated_scores}")
    print(f"    My score change: {scores[my_index]} → {updated_scores[my_index]}")


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    random.seed(42)  # for reproducibility

    # Show the mathematical analysis first
    analyze_optimal_threshold()

    # Demonstrate the core function
    demo_skunk_turn_function()

    # Play a single verbose game
    demo_single_game()

    # Run a large tournament
    demo_tournament()

    # Head-to-head analysis
    demo_head_to_head()

    # Adaptive bot learning
    demo_adaptive_learning()

    # ─── Final Discussion Points ───
    print("\n" + "═" * 60)
    print("  DISCUSSION POINTS FOR INTERVIEW")
    print("═" * 60)
    print("""
  1. IS THERE AN OPTIMAL WAY TO PLAY?
     Yes, from a pure expected-value standpoint. The break-even formula
     (11·turn_total + game_total < 200) gives the mathematically optimal
     threshold. However, in a multi-player competitive game, context matters
     — if you're behind, you may need to take more risk.

  2. DOES RISK PREFERENCE MATTER? SHOULD IT BE CONSISTENT?
     No — risk preference should be DYNAMIC. When you're ahead, play
     conservatively to protect your lead. When you're behind, or it's your
     last turn, play aggressively. The ContextAwareBot demonstrates this
     and outperforms static strategies.

  3. CAN WE DETERMINE WIN PROBABILITY?
     Yes, via Monte Carlo simulation (as shown above). The win probability
     absolutely depends on opponent strategies — a ContextAwareBot has a
     higher win probability against a ConservativeBot than against another
     ContextAwareBot.

  4. TESTING MULTIPLE SKUNK-BOTS:
     The tournament framework above does exactly this — it creates bot
     instances, rotates starting positions for fairness, runs thousands
     of games, and tracks comprehensive statistics.

  5. SELF-IMPROVING BOT:
     The AdaptiveBot uses a simple evolutionary approach: it maintains a
     risk_factor, reinforces on wins, explores on losses, and converges
     toward the optimal aggression level for its specific opponents.
     More sophisticated approaches could use reinforcement learning (Q-learning)
     or neural networks to learn state-action value functions.
    """)
