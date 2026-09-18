"""Head-to-head tournament with confidence intervals.

The README describes the ExpectedValue rule as optimal. That rule
(stop when 11*turn_total + game_total >= 200) is the one-roll break-even on
*expected points*. Maximising expected points per turn is not the same objective
as maximising the probability of winning a race to a target, so this benchmark
measures win probability directly.

Every pairing plays the same number of games with seats alternated, so neither
bot gets a first-mover advantage. Results carry 95% Wilson intervals, and a
pairing is only called a win when the interval excludes 50%.

Run: python benchmarks/tournament.py [--games 4000] [--seed 17] [--json out.json]
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skunk_game import (  # noqa: E402
    AggressiveBot,
    ConservativeBot,
    ContextAwareBot,
    ExpectedValueBot,
    FixedRollBot,
    RandomBot,
    play_game,
    verify_ev_formula_empirically,
)

# MonteCarloBot is excluded from the default roster: at 200 rollouts per
# decision a full round robin takes minutes, not seconds, which is wrong for CI.
ROSTER = {
    "ExpectedValue": ExpectedValueBot,
    "ContextAware": ContextAwareBot,
    "Conservative(15)": lambda: ConservativeBot(15),
    "Aggressive(30)": lambda: AggressiveBot(30),
    "FixedRoll(3)": lambda: FixedRollBot(3),
    "Random(60%)": lambda: RandomBot(0.6),
}


def wilson(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (centre - half, centre + half)


def head_to_head(make_a, make_b, games: int) -> int:
    """Games won by A out of `games`, seats alternated each game."""
    a_wins = 0
    for g in range(games):
        a, b = make_a(), make_b()
        if g % 2 == 0:
            winner, _ = play_game([a, b], target=100)
            a_wins += winner == 0
        else:
            winner, _ = play_game([b, a], target=100)
            a_wins += winner == 1
    return a_wins


def run(games: int, seed: int) -> dict:
    random.seed(seed)
    names = list(ROSTER)
    matrix: dict[str, dict[str, dict]] = {n: {} for n in names}

    for a, b in itertools.combinations(names, 2):
        wins = head_to_head(ROSTER[a], ROSTER[b], games)
        lo, hi = wilson(wins, games)
        matrix[a][b] = {"wins": wins, "games": games, "rate": wins / games, "ci": (lo, hi)}
        matrix[b][a] = {"wins": games - wins, "games": games, "rate": 1 - wins / games, "ci": (1 - hi, 1 - lo)}

    overall = {}
    for n in names:
        w = sum(v["wins"] for v in matrix[n].values())
        g = sum(v["games"] for v in matrix[n].values())
        overall[n] = {"wins": w, "games": g, "rate": w / g, "ci": wilson(w, g)}

    return {"games_per_pairing": games, "seed": seed, "matrix": matrix, "overall": overall}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    random.seed(args.seed)
    ev_ok = verify_ev_formula_empirically(num_trials=50_000)
    print(f"EV break-even formula empirically verified: {ev_ok}\n")

    res = run(args.games, args.seed)
    ranked = sorted(res["overall"].items(), key=lambda kv: -kv[1]["rate"])

    print(f"Round robin: {args.games} games per pairing, seats alternated, seed {args.seed}\n")
    print(f"{'bot':<18}{'win rate':>10}{'95% CI':>18}")
    print("-" * 46)
    for name, o in ranked:
        lo, hi = o["ci"]
        print(f"{name:<18}{o['rate']:>10.1%}   [{lo:.1%}, {hi:.1%}]")

    print("\nExpectedValue head to head:")
    for opp, r in sorted(res["matrix"]["ExpectedValue"].items(), key=lambda kv: -kv[1]["rate"]):
        lo, hi = r["ci"]
        verdict = "wins" if lo > 0.5 else "loses" if hi < 0.5 else "no significant difference"
        print(f"  vs {opp:<18}{r['rate']:>7.1%}  [{lo:.1%}, {hi:.1%}]  {verdict}")

    if args.json:
        args.json.write_text(json.dumps({"ev_formula_verified": ev_ok, **res}, indent=2, default=list) + "\n")
        print(f"\nWrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
