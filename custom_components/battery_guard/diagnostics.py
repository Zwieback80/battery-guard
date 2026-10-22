# Projekt: Battery Guard
# Copyright (c) 2026 Christian Brandt
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Lizenz: https://polyformproject.org/licenses/noncommercial/1.0.0
#
# Kommerzielle Nutzung ist durch diese Lizenz nicht gestattet.
# Einzelheiten und Ausnahmen ergeben sich aus dem vollständigen Lizenztext.

"""Diagnostics support for Battery Guard."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import BatteryGuardCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: BatteryGuardCoordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "options": dict(entry.options),
        "monitored_devices": [
            {
                "entity_id": status.entity_id,
                "name": status.name,
                "area": status.area,
                "kind": status.kind,
                "status": status.status,
                "level": status.level,
                "is_offline": status.is_offline,
            }
            for status in coordinator.data.values()
        ],
    }
