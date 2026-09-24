"""Monte Carlo trade-resampling simulation (Middle Layer 2: quant/risk).

Ported from Arima Finance Engine v3 ``modules/monte_carlo_analytics.py``
(commit dc6e1d7) with identical resampling, ruin, drawdown and percentile
semantics, so identical inputs and seed give identical summaries. Two v3
behaviours are deliberately not ported because they fabricate values:
invalid P&L entries silently becoming ``0.0``, and initial equity inferred
from the first trade. Here both must be supplied and valid, or the request
is rejected.

This is research only. It reads caller-supplied history, persists nothing,
and has no path to execution.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from statistics import mean, median

ALGORITHM = "bootstrap_trade_resampling"
ALGORITHM_VERSION = "1.0.0"
ALGORITHM_ORIGIN = "arima-finance-engine-v3:modules/monte_carlo_analytics.py@dc6e1d7"
MIN_SIMULATIONS = 10_000
MAX_SIMULATIONS = 50_000
MAX_TRADES = 5_000
MAX_WORK = 10_000_000


class SimulationInputError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MonteCarloSummary:
    simulations: int
    trades_per_simulation: int
    initial_equity: float
    probability_of_profit: float
    probability_of_loss: float
    probability_of_new_equity_high: float
    probability_of_ruin: float
    expected_final_equity: float
    median_final_equity: float
    best_final_equity: float
    worst_final_equity: float
    maximum_simulated_drawdown: float
    average_simulated_drawdown: float
    confidence_interval_95: tuple[float, float]
    confidence_interval_99: tuple[float, float]
    seed: int
    input_sha256: str


def percentile(values: list[float], percentage: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentage / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def input_fingerprint(profits: list[float], initial_equity: float) -> str:
    payload = json.dumps(
        {"profits": profits, "initial_equity": initial_equity},
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def validate(profits: list[float], initial_equity: float, simulations: int) -> None:
    if not profits:
        raise SimulationInputError("At least one historical trade result is required")
    if len(profits) > MAX_TRADES:
        raise SimulationInputError(f"At most {MAX_TRADES} trade results are accepted")
    if any(not math.isfinite(value) for value in profits):
        raise SimulationInputError("Trade results must be finite numbers")
    if not math.isfinite(initial_equity) or initial_equity <= 0:
        raise SimulationInputError("Initial equity must be a positive finite number")
    if not MIN_SIMULATIONS <= simulations <= MAX_SIMULATIONS:
        raise SimulationInputError(
            f"Simulations must be between {MIN_SIMULATIONS} and {MAX_SIMULATIONS}"
        )
    if simulations * len(profits) > MAX_WORK:
        raise SimulationInputError("Simulation size exceeds the computation budget")


def run_monte_carlo(
    profits: list[float],
    *,
    initial_equity: float,
    simulations: int = MIN_SIMULATIONS,
    seed: int = 0,
) -> MonteCarloSummary:
    validate(profits, initial_equity, simulations)
    historical_peak = initial_equity
    running = initial_equity
    for profit in profits:
        running += profit
        historical_peak = max(historical_peak, running)

    generator = random.Random(seed)
    final_equities: list[float] = []
    drawdowns: list[float] = []
    ruined_count = 0
    new_high_count = 0
    for _ in range(simulations):
        equity = initial_equity
        peak = initial_equity
        maximum_drawdown = 0.0
        ruined = equity <= 0
        curve_high = round(equity, 6)
        for _ in profits:
            equity += generator.choice(profits)
            peak = max(peak, equity)
            maximum_drawdown = max(maximum_drawdown, peak - equity)
            ruined = ruined or equity <= 0
            curve_high = max(curve_high, round(equity, 6))
        final_equities.append(equity)
        drawdowns.append(maximum_drawdown)
        ruined_count += ruined
        new_high_count += curve_high > historical_peak

    profitable = sum(value > initial_equity for value in final_equities)
    losing = sum(value < initial_equity for value in final_equities)
    return MonteCarloSummary(
        simulations=simulations,
        trades_per_simulation=len(profits),
        initial_equity=round(initial_equity, 6),
        probability_of_profit=round(profitable / simulations * 100, 6),
        probability_of_loss=round(losing / simulations * 100, 6),
        probability_of_new_equity_high=round(new_high_count / simulations * 100, 6),
        probability_of_ruin=round(ruined_count / simulations * 100, 6),
        expected_final_equity=round(mean(final_equities), 6),
        median_final_equity=round(median(final_equities), 6),
        best_final_equity=round(max(final_equities), 6),
        worst_final_equity=round(min(final_equities), 6),
        maximum_simulated_drawdown=round(max(drawdowns), 6),
        average_simulated_drawdown=round(mean(drawdowns), 6),
        confidence_interval_95=(
            round(percentile(final_equities, 2.5), 6),
            round(percentile(final_equities, 97.5), 6),
        ),
        confidence_interval_99=(
            round(percentile(final_equities, 0.5), 6),
            round(percentile(final_equities, 99.5), 6),
        ),
        seed=seed,
        input_sha256=input_fingerprint(profits, initial_equity),
    )
