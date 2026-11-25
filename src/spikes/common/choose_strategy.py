"""Pick the better strategy (baseline or think) from Phase A, for runs nobody is watching.

Used by grace_unattended.sh between Phase A and Phases B/C. Reads one summary.csv (one
model and one --native-think setting per folder) and prints the winning strategy name.

The rule is the one in qwen3/FINDINGS-gpu.md, section 6:
  1. most dates + weights correct (summed over all outlines),
  2. then most items found + TBD flags correct,
  3. a tie goes to baseline, because it is faster (one call instead of two).
Only normal runs count (injected runs are skipped).

Usage: python choose_strategy.py results/qwen3-4b_think-off/summary.csv
"""

from __future__ import annotations

import csv
import sys


def totals_per_strategy(summary_path: str) -> dict:
    """Sum the correct dates, weights, found items and TBD flags for each strategy."""
    totals = {}
    with open(summary_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            # Injected runs belong to Phase C, not to the choice
            if row["injected"] != "False":
                continue
            key_items = int(row["key_assessments"])
            strategy_totals = totals.setdefault(row["strategy"], {"dates": 0.0, "weights": 0.0,
                                                                  "found": 0.0, "tbd": 0.0})
            # Accuracies are fractions of the key items, so multiply back to item counts
            strategy_totals["dates"] += float(row["date_accuracy"]) * key_items
            strategy_totals["weights"] += float(row["weight_accuracy"]) * key_items
            strategy_totals["tbd"] += float(row["tbd_accuracy"]) * key_items
            strategy_totals["found"] += int(row["found"])
    return totals


def rank(strategy_totals: dict) -> tuple:
    """Bigger is better: dates + weights first, then found + TBD."""
    return (round(strategy_totals["dates"] + strategy_totals["weights"], 3),
            round(strategy_totals["found"] + strategy_totals["tbd"], 3))


def main() -> None:
    totals = totals_per_strategy(sys.argv[1])
    if not totals:
        sys.exit(f"No normal runs in {sys.argv[1]}")

    # Show the totals on stderr so the pipeline log records why the choice was made
    for name, t in sorted(totals.items()):
        print(f"{name}: dates {t['dates']:.0f}, weights {t['weights']:.0f}, "
              f"found {t['found']:.0f}, TBD {t['tbd']:.0f}", file=sys.stderr)

    best = "baseline" if "baseline" in totals else next(iter(totals))
    for name, t in totals.items():
        if rank(t) > rank(totals[best]):
            best = name
    # Only the strategy name goes to stdout, so the shell can read it
    print(best)


if __name__ == "__main__":
    main()
