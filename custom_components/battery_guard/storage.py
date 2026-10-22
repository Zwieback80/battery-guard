# Projekt: Battery Guard
# Copyright (c) 2026 Christian Brandt
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Lizenz: https://polyformproject.org/licenses/noncommercial/1.0.0
#
# Kommerzielle Nutzung ist durch diese Lizenz nicht gestattet.
# Einzelheiten und Ausnahmen ergeben sich aus dem vollständigen Lizenztext.

"""Persistent storage for battery change history.

Uses Home Assistant's own Store helper (writes to .storage/, survives
restarts) rather than the recorder — this is small, structured data
that should never be purged by a recorder history-retention setting.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

STORAGE_VERSION = 1
STORAGE_KEY = "battery_guard_history"

MAX_CHANGES_KEPT = 20  # per device — a rolling log, not an unbounded one
DEFAULT_QUANTITY = 1


def _default_device_entry() -> dict[str, Any]:
    return {"battery_type": None, "quantity": DEFAULT_QUANTITY, "changes": []}


class BatteryGuardHistoryStore:
    """In-memory cache of battery-change history, backed by Store."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] = {"devices": {}}

    async def async_load(self) -> None:
        loaded = await self._store.async_load()
        if loaded:
            self._data = loaded
            self._data.setdefault("devices", {})
            # Backfill "quantity" for devices saved before this field existed.
            for entry in self._data["devices"].values():
                entry.setdefault("quantity", DEFAULT_QUANTITY)

    def get_device_history(self, source_entity_id: str) -> dict[str, Any]:
        """Return {'battery_type', 'quantity', 'changes': [...]} for a device."""
        return self._data["devices"].get(source_entity_id, _default_device_entry())

    def get_missing_since(self) -> dict[str, datetime]:
        """Return {source_entity_id: first_time_seen_missing}, persisted across restarts."""
        result: dict[str, datetime] = {}
        for source_entity_id, raw in self._data.get("missing_since", {}).items():
            parsed = dt_util.parse_datetime(raw)
            if parsed is not None:
                result[source_entity_id] = parsed
        return result

    async def async_save_missing_since(self, missing: dict[str, datetime]) -> None:
        """Persist the 'missing since' timers (only writes when something changed)."""
        serialised = {key: value.isoformat() for key, value in missing.items()}
        if self._data.get("missing_since", {}) == serialised:
            return
        self._data["missing_since"] = serialised
        await self._store.async_save(self._data)

    async def async_set_battery_info(
        self,
        source_entity_id: str,
        battery_type: str | None,
        quantity: int | None = None,
    ) -> None:
        """Declare what battery a device needs, independent of any change event.

        Used to pre-configure a device (e.g. "this remote needs 2x AA")
        before any change has ever been logged for it, so the shopping
        list can be accurate from day one.
        """
        devices = self._data.setdefault("devices", {})
        entry = devices.setdefault(source_entity_id, _default_device_entry())
        if battery_type:
            entry["battery_type"] = battery_type
        if quantity is not None:
            entry["quantity"] = quantity
        await self._store.async_save(self._data)

    async def async_log_change(
        self,
        source_entity_id: str,
        battery_type: str | None,
        note: str | None,
        when: datetime | None = None,
        quantity: int | None = None,
    ) -> None:
        when = when or dt_util.utcnow()
        devices = self._data.setdefault("devices", {})
        entry = devices.setdefault(source_entity_id, _default_device_entry())

        entry["changes"].append(
            {
                "date": when.isoformat(),
                "battery_type": battery_type,
                "note": note,
            }
        )
        entry["changes"] = entry["changes"][-MAX_CHANGES_KEPT:]

        if battery_type:
            entry["battery_type"] = battery_type
        if quantity is not None:
            entry["quantity"] = quantity

        await self._store.async_save(self._data)

    async def async_clear_history(self, source_entity_id: str) -> bool:
        """Remove all logged changes (and the remembered battery info) for a device.

        Returns False if the device had no history to clear — lets the
        caller give an accurate "nothing to do" response.
        """
        devices = self._data.setdefault("devices", {})
        if source_entity_id not in devices:
            return False
        del devices[source_entity_id]
        await self._store.async_save(self._data)
        return True
