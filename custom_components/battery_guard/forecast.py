# Projekt: Battery Guard
# Copyright (c) 2026 Christian Brandt
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Lizenz: https://polyformproject.org/licenses/noncommercial/1.0.0
#
# Kommerzielle Nutzung ist durch diese Lizenz nicht gestattet.
# Einzelheiten und Ausnahmen ergeben sich aus dem vollständigen Lizenztext.

"""Consumption forecasting for battery-level entities.

Fetches recent history from Home Assistant's recorder and fits a simple
linear trend (least-squares) to estimate:

- the drain rate in %/day
- days remaining until the critical threshold is reached

This intentionally stays simple (a straight-line fit) rather than a
more elaborate model — battery drain is close enough to linear over a
1-2 week window for the purpose ("should I worry this week or not"),
and a simple model is easy to reason about when the number looks odd.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

TREND_FALLING = "falling"
TREND_STABLE = "stable"
TREND_RISING = "rising"
TREND_UNKNOWN = "unknown"

# A rate flatter than this (%/day) is treated as noise, not a real trend —
# avoids reporting "stable" vs "falling" flip-flopping on tiny fluctuations.
FLAT_RATE_THRESHOLD = 0.05
MIN_DATA_POINTS = 3


@dataclass
class ForecastResult:
    rate_per_day: float | None  # negative = draining
    days_remaining: float | None
    trend: str


def _linear_regression_slope(points: list[tuple[float, float]]) -> float | None:
    """Least-squares slope (y per hour) for (hours_elapsed, percent) points."""
    n = len(points)
    if n < 2:
        return None
    sum_x = sum(p[0] for p in points)
    sum_y = sum(p[1] for p in points)
    sum_xx = sum(p[0] * p[0] for p in points)
    sum_xy = sum(p[0] * p[1] for p in points)
    denominator = n * sum_xx - sum_x * sum_x
    if denominator == 0:
        return None
    return (n * sum_xy - sum_x * sum_y) / denominator


async def async_forecast_entity(
    hass: HomeAssistant,
    entity_id: str,
    current_level: float,
    critical_threshold: float,
    history_days: int,
) -> ForecastResult:
    """Estimate the consumption trend for a single battery-level entity."""
    try:
        from homeassistant.components.recorder import get_instance, history
    except ImportError:
        # Recorder integration not loaded/available.
        return ForecastResult(None, None, TREND_UNKNOWN)

    end_time = dt_util.utcnow()
    start_time = end_time - timedelta(days=history_days)

    def _fetch():
        return history.state_changes_during_period(
            hass,
            start_time,
            end_time,
            entity_id,
            include_start_time_state=True,
            no_attributes=True,
        )

    try:
        recorder_instance = get_instance(hass)
        result = await recorder_instance.async_add_executor_job(_fetch)
    except Exception:  # noqa: BLE001 - recorder may be disabled/unavailable
        _LOGGER.debug(
            "Battery Guard: history lookup failed for %s", entity_id, exc_info=True
        )
        return ForecastResult(None, None, TREND_UNKNOWN)

    states = result.get(entity_id, [])
    points: list[tuple[float, float]] = []
    for state in states:
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            continue
        hours_elapsed = (state.last_changed - start_time).total_seconds() / 3600
        points.append((hours_elapsed, value))

    if len(points) < MIN_DATA_POINTS:
        return ForecastResult(None, None, TREND_UNKNOWN)

    slope_per_hour = _linear_regression_slope(points)
    if slope_per_hour is None:
        return ForecastResult(None, None, TREND_UNKNOWN)

    rate_per_day = round(slope_per_hour * 24, 3)

    if rate_per_day > FLAT_RATE_THRESHOLD:
        return ForecastResult(rate_per_day, None, TREND_RISING)
    if rate_per_day >= -FLAT_RATE_THRESHOLD:
        return ForecastResult(rate_per_day, None, TREND_STABLE)

    days_remaining = (current_level - critical_threshold) / abs(rate_per_day)
    days_remaining = max(0.0, round(days_remaining, 1))
    return ForecastResult(rate_per_day, days_remaining, TREND_FALLING)
