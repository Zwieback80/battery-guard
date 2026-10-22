# Projekt: Battery Guard
# Copyright (c) 2026 Christian Brandt
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Lizenz: https://polyformproject.org/licenses/noncommercial/1.0.0
#
# Kommerzielle Nutzung ist durch diese Lizenz nicht gestattet.
# Einzelheiten und Ausnahmen ergeben sich aus dem vollständigen Lizenztext.

"""Coordinator: periodically refreshes battery status for all discovered entities."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AUTO_LOG_CHANGES,
    CONF_AUTO_LOG_JUMP_THRESHOLD,
    CONF_CRITICAL_THRESHOLD,
    CONF_EXCLUDED_ENTITIES,
    CONF_FORECAST_INTERVAL_HOURS,
    CONF_HISTORY_DAYS,
    CONF_INCLUDED_ENTITIES,
    CONF_LOW_THRESHOLD,
    CONF_OFFLINE_HOURS,
    CONF_STALE_GRACE_HOURS,
    CONF_WARN_THRESHOLD,
    DEFAULT_AUTO_LOG_CHANGES,
    DEFAULT_AUTO_LOG_JUMP_THRESHOLD,
    DEFAULT_CRITICAL_THRESHOLD,
    DEFAULT_FORECAST_INTERVAL_HOURS,
    DEFAULT_HISTORY_DAYS,
    DEFAULT_LOW_THRESHOLD,
    DEFAULT_OFFLINE_HOURS,
    DEFAULT_STALE_GRACE_HOURS,
    DEFAULT_WARN_THRESHOLD,
    DOMAIN,
    STATUS_CRITICAL,
    STATUS_LOW,
    STATUS_OFFLINE,
    STATUS_OK,
    STATUS_UNKNOWN,
    STATUS_WATCH,
)
from .discovery import DiscoveredBatteryEntity, async_discover_battery_entities
from .forecast import ForecastResult, TREND_UNKNOWN, async_forecast_entity
from .health import compute_health_score
from .maintenance import async_cleanup_stale_devices, async_sync_device_areas
from .storage import BatteryGuardHistoryStore

_LOGGER = logging.getLogger(__name__)


@dataclass
class BatteryGuardDeviceStatus:
    """Computed status for one monitored device."""

    entity_id: str
    name: str
    area: str | None
    kind: str
    status: str
    level: float | None
    last_seen: datetime | None
    is_offline: bool
    consumption_rate_per_day: float | None = None
    days_remaining: float | None = None
    trend: str = TREND_UNKNOWN
    health_score: int | None = None
    health_level_score: int | None = None
    health_trend_score: int | None = None
    health_reliability_score: int | None = None


class BatteryGuardCoordinator(DataUpdateCoordinator[dict[str, BatteryGuardDeviceStatus]]):
    """Coordinates discovery + classification of all battery entities."""

    def __init__(
        self, hass: HomeAssistant, entry, history_store: BatteryGuardHistoryStore
    ) -> None:
        self.entry = entry
        self._history_store = history_store
        options = entry.options or {}
        interval_minutes = options.get("scan_interval_minutes", 5)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=interval_minutes),
        )
        # entity_id -> (computed_at, ForecastResult). History queries are
        # comparatively expensive, so these are only refreshed every
        # forecast_interval_hours, not on every regular poll.
        self._forecast_cache: dict[str, tuple[datetime, ForecastResult]] = {}
        # entity_id -> last-seen level, used to detect a sudden upward jump
        # (a likely battery replacement) between consecutive polls.
        self._previous_levels: dict[str, float] = {}
        # source_entity_id -> when it was first observed missing from
        # discovery, used by the stale-device cleanup below. Persisted so
        # that restarts do not keep resetting the grace period.
        self._missing_since: dict[str, datetime] = history_store.get_missing_since()

    def _thresholds(self) -> tuple[float, float, float, float]:
        options = self.entry.options or {}
        warn = options.get(CONF_WARN_THRESHOLD, DEFAULT_WARN_THRESHOLD)
        low = options.get(CONF_LOW_THRESHOLD, DEFAULT_LOW_THRESHOLD)
        critical = options.get(CONF_CRITICAL_THRESHOLD, DEFAULT_CRITICAL_THRESHOLD)
        offline_hours = options.get(CONF_OFFLINE_HOURS, DEFAULT_OFFLINE_HOURS)
        return warn, low, critical, offline_hours

    def _forecast_settings(self) -> tuple[int, int]:
        options = self.entry.options or {}
        history_days = options.get(CONF_HISTORY_DAYS, DEFAULT_HISTORY_DAYS)
        interval_hours = options.get(CONF_FORECAST_INTERVAL_HOURS, DEFAULT_FORECAST_INTERVAL_HOURS)
        return history_days, interval_hours

    def _auto_log_settings(self) -> tuple[bool, float]:
        options = self.entry.options or {}
        enabled = options.get(CONF_AUTO_LOG_CHANGES, DEFAULT_AUTO_LOG_CHANGES)
        threshold = options.get(CONF_AUTO_LOG_JUMP_THRESHOLD, DEFAULT_AUTO_LOG_JUMP_THRESHOLD)
        return enabled, threshold

    def _is_rechargeable(self, entity_id: str) -> bool:
        """Best-effort guess: does this device also expose a charging-state
        sensor (e.g. ``..._battery_state`` reporting charging/discharging/full)?
        That's the signature of a rechargeable device (phone, tablet) — a
        level jump there is just normal charging, not a battery swap."""
        if entity_id.endswith("_battery_level"):
            sibling = entity_id[: -len("_battery_level")] + "_battery_state"
            if self.hass.states.get(sibling) is not None:
                return True
        return False

    async def _maybe_auto_log_change(self, entity_id: str, level: float) -> None:
        enabled, threshold = self._auto_log_settings()
        previous = self._previous_levels.get(entity_id)
        self._previous_levels[entity_id] = level

        if not enabled or previous is None:
            return
        if level - previous < threshold:
            return
        if self._is_rechargeable(entity_id):
            return

        if (self.hass.config.language or "").startswith("de"):
            note = f"Automatisch erkannt: Sprung von {previous:.0f}% auf {level:.0f}%"
        else:
            note = f"Detected automatically: jump from {previous:.0f}% to {level:.0f}%"
        await self._history_store.async_log_change(entity_id, None, note)

    async def _async_get_forecast(
        self, entity_id: str, level: float, critical_threshold: float
    ) -> ForecastResult:
        """Return a cached forecast, recomputing only every forecast_interval_hours."""
        history_days, interval_hours = self._forecast_settings()
        now = dt_util.utcnow()

        cached = self._forecast_cache.get(entity_id)
        if cached is not None:
            computed_at, result = cached
            if now - computed_at < timedelta(hours=interval_hours):
                return result

        result = await async_forecast_entity(
            self.hass, entity_id, level, critical_threshold, history_days
        )
        self._forecast_cache[entity_id] = (now, result)
        return result

    def _classify_level(self, level: float, warn: float, low: float, critical: float) -> str:
        if level < critical:
            return STATUS_CRITICAL
        if level < low:
            return STATUS_LOW
        if level < warn:
            return STATUS_WATCH
        return STATUS_OK

    async def _async_update_data(self) -> dict[str, BatteryGuardDeviceStatus]:
        options = self.entry.options or {}
        include = options.get(CONF_INCLUDED_ENTITIES)
        exclude = options.get(CONF_EXCLUDED_ENTITIES, [])

        # Discovery only touches the state machine / registries, which are
        # safe to read directly from the event loop (no blocking I/O).
        discovered: list[DiscoveredBatteryEntity] = async_discover_battery_entities(
            self.hass, include, exclude
        )

        warn, low, critical, offline_hours = self._thresholds()
        offline_delta = timedelta(hours=offline_hours)
        now = dt_util.utcnow()

        results: dict[str, BatteryGuardDeviceStatus] = {}

        for item in discovered:
            state = self.hass.states.get(item.entity_id)
            if state is None:
                results[item.entity_id] = BatteryGuardDeviceStatus(
                    entity_id=item.entity_id,
                    name=item.name,
                    area=item.area,
                    kind=item.kind,
                    status=STATUS_UNKNOWN,
                    level=None,
                    last_seen=None,
                    is_offline=True,
                )
                continue

            # last_reported also advances when a device re-sends an unchanged
            # value; last_changed would make stable batteries look offline.
            last_seen = state.last_reported or state.last_updated
            is_offline = bool(last_seen) and (now - last_seen) > offline_delta

            if item.kind == "level":
                try:
                    level = float(state.state)
                except (TypeError, ValueError):
                    level = None
                else:
                    if not is_offline:
                        await self._maybe_auto_log_change(item.entity_id, level)
            else:
                # binary battery sensor: "on" == battery low, no percentage
                level = None

            if is_offline:
                status = STATUS_OFFLINE
            elif item.kind == "level" and level is not None:
                status = self._classify_level(level, warn, low, critical)
            elif item.kind == "binary":
                status = STATUS_CRITICAL if state.state == "on" else STATUS_OK
            else:
                status = STATUS_UNKNOWN

            rate_per_day: float | None = None
            days_remaining: float | None = None
            trend = TREND_UNKNOWN
            if item.kind == "level" and level is not None and not is_offline:
                forecast = await self._async_get_forecast(item.entity_id, level, critical)
                rate_per_day = forecast.rate_per_day
                days_remaining = forecast.days_remaining
                trend = forecast.trend

            health = compute_health_score(
                kind=item.kind,
                status=status,
                level=level,
                trend=trend,
                days_remaining=days_remaining,
                is_offline=is_offline,
                critical_threshold=critical,
            )

            results[item.entity_id] = BatteryGuardDeviceStatus(
                entity_id=item.entity_id,
                name=item.name,
                area=item.area,
                kind=item.kind,
                status=status,
                level=level,
                last_seen=last_seen,
                is_offline=is_offline,
                consumption_rate_per_day=rate_per_day,
                days_remaining=days_remaining,
                trend=trend,
                health_score=health.score,
                health_level_score=health.level_score,
                health_trend_score=health.trend_score,
                health_reliability_score=health.reliability_score,
            )

        # Keep every device in the room of its source entity (or in the
        # fallback area), then remove devices that are no longer needed.
        async_sync_device_areas(self.hass, self.entry.entry_id, discovered)
        await self._async_cleanup_stale(discovered)

        return results

    async def _async_cleanup_stale(self, discovered: list[DiscoveredBatteryEntity]) -> None:
        options = self.entry.options or {}
        grace_hours = options.get(CONF_STALE_GRACE_HOURS, DEFAULT_STALE_GRACE_HOURS)
        if grace_hours <= 0:
            # 0 disables cleanup entirely — an explicit opt-out.
            return

        discovered_entity_ids = {item.entity_id for item in discovered}
        removed = await async_cleanup_stale_devices(
            hass=self.hass,
            entry_id=self.entry.entry_id,
            discovered_entity_ids=discovered_entity_ids,
            missing_since=self._missing_since,
            grace=timedelta(hours=grace_hours),
            now=dt_util.utcnow(),
        )

        await self._history_store.async_save_missing_since(self._missing_since)

        if not removed:
            return

        names = ", ".join(removed)
        if (self.hass.config.language or "").startswith("de"):
            title = "Battery Guard: Geräte entfernt"
            message = (
                f"Folgende Geräte wurden seit mehr als {grace_hours} Stunden nicht "
                f"mehr gefunden und automatisch entfernt: {names}."
            )
        else:
            title = "Battery Guard: devices removed"
            message = (
                f"These devices have not been found for more than {grace_hours} hours "
                f"and were removed automatically: {names}."
            )
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": title,
                "message": message,
                "notification_id": f"{DOMAIN}_stale_cleanup",
            },
            blocking=False,
        )
