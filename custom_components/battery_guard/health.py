# Projekt: Battery Guard
# Copyright (c) 2026 Christian Brandt
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Lizenz: https://polyformproject.org/licenses/noncommercial/1.0.0
#
# Kommerzielle Nutzung ist durch diese Lizenz nicht gestattet.
# Einzelheiten und Ausnahmen ergeben sich aus dem vollständigen Lizenztext.

"""Battery Health Score: a single 0-100 number combining three factors.

Deliberately transparent rather than a black box — the sub-scores are
exposed as attributes so a suspicious-looking score can be explained,
not just trusted.

- **Level score** (50% weight): where the current reading sits between
  the critical threshold (0) and full (100).
- **Trend score** (30% weight): how many days of runway remain at the
  current drain rate, relative to a 60-day "healthy" horizon. Devices
  with no usable trend yet (too little history) get a neutral score
  rather than being penalised for lack of data.
- **Reliability score** (20% weight): 0 if the device is currently
  considered offline (not reporting), 100 otherwise. A battery reading
  is only as good as the device delivering it.
"""
from __future__ import annotations

from dataclasses import dataclass

from .const import STATUS_CRITICAL, STATUS_OFFLINE
from .forecast import TREND_FALLING, TREND_RISING, TREND_STABLE, TREND_UNKNOWN

LEVEL_WEIGHT = 0.5
TREND_WEIGHT = 0.3
RELIABILITY_WEIGHT = 0.2

# A device that would still last this many days at its current drain
# rate is considered to have a "perfect" trend score.
HEALTHY_HORIZON_DAYS = 60

# Neutral sub-score used when there isn't enough data to judge trend —
# absence of evidence shouldn't be scored as bad evidence.
NEUTRAL_TREND_SCORE = 70


@dataclass
class HealthScoreResult:
    score: int
    level_score: int
    trend_score: int
    reliability_score: int


def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def _level_score(level: float | None, critical_threshold: float) -> int:
    if level is None:
        return NEUTRAL_TREND_SCORE
    span = 100 - critical_threshold
    if span <= 0:
        return 100 if level >= critical_threshold else 0
    return round(_clamp(100 * (level - critical_threshold) / span))


def _binary_level_score(status: str) -> int:
    # Binary battery sensors only ever report "low" or "ok" — no
    # percentage, so the level score collapses to those two states.
    return 0 if status == STATUS_CRITICAL else 100


def _trend_score(trend: str, days_remaining: float | None) -> int:
    if trend in (TREND_STABLE, TREND_RISING):
        return 100
    if trend == TREND_FALLING and days_remaining is not None:
        return round(_clamp(100 * days_remaining / HEALTHY_HORIZON_DAYS))
    return NEUTRAL_TREND_SCORE  # TREND_UNKNOWN, or falling with no estimate yet


def _reliability_score(is_offline: bool) -> int:
    return 0 if is_offline else 100


def compute_health_score(
    kind: str,
    status: str,
    level: float | None,
    trend: str,
    days_remaining: float | None,
    is_offline: bool,
    critical_threshold: float,
) -> HealthScoreResult:
    """Compute the 0-100 health score and its three sub-scores."""
    if kind == "level":
        level_score = _level_score(level, critical_threshold)
    else:
        level_score = _binary_level_score(status)

    trend_score = _trend_score(trend, days_remaining) if kind == "level" else NEUTRAL_TREND_SCORE
    reliability_score = _reliability_score(is_offline)

    total = (
        LEVEL_WEIGHT * level_score
        + TREND_WEIGHT * trend_score
        + RELIABILITY_WEIGHT * reliability_score
    )

    return HealthScoreResult(
        score=round(_clamp(total)),
        level_score=level_score,
        trend_score=trend_score,
        reliability_score=reliability_score,
    )
