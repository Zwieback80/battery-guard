# Projekt: Battery Guard
# Copyright (c) 2026 Christian Brandt
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Lizenz: https://polyformproject.org/licenses/noncommercial/1.0.0
#
# Kommerzielle Nutzung ist durch diese Lizenz nicht gestattet.
# Einzelheiten und Ausnahmen ergeben sich aus dem vollständigen Lizenztext.

"""Automatic upkeep of Battery Guard devices.

Two jobs, both fully automatic and run on every coordinator refresh:

1. **Room sync** - every Battery Guard device is kept in the room of its
   source entity. Sources without a room are filed under a fallback area
   ("Sonstiges" or "Other" by language, created on demand). Rooms set by hand on a Battery Guard
   device or its entities are deliberately not respected: the room is
   always taken from the source, so the result is the same on every
   installation. To move a device, change the room of the *source* device.

2. **Stale cleanup** - when a physical device is replaced or a source
   entity is renamed, the Battery Guard "shadow" device created for the
   old source would linger forever as an "unavailable" ghost. Shadow
   devices are removed when their source has been missing for longer than
   a configurable grace period (default 72 h), which is long enough to
   ride out a sleepy battery node's check-in cadence or a temporary
   Z-Wave/Zigbee hiccup. Shadow devices that have no entities left at all
   are removed immediately, because they cannot show anything anyway.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, FALLBACK_AREA_NAMES, OVERVIEW_IDENTIFIER
from .discovery import DiscoveredBatteryEntity

_LOGGER = logging.getLogger(__name__)


def async_get_tracked_devices(hass: HomeAssistant, entry_id: str) -> dict[str, str]:
    """Return {source_entity_id: device_id} for every Battery Guard shadow device.

    The household overview device is not a shadow device (it has no source
    entity) and is therefore excluded.
    """
    device_registry = dr.async_get(hass)
    result: dict[str, str] = {}
    for device in dr.async_entries_for_config_entry(device_registry, entry_id):
        for domain, identifier in device.identifiers:
            if domain == DOMAIN and identifier != OVERVIEW_IDENTIFIER:
                result[identifier] = device.id
    return result


def _async_get_fallback_area_id(hass: HomeAssistant, area_registry: ar.AreaRegistry) -> str:
    """Return the id of the fallback area, creating it in the HA language if needed."""
    for name in FALLBACK_AREA_NAMES.values():
        existing = area_registry.async_get_area_by_name(name)
        if existing is not None:
            return existing.id
    language = (hass.config.language or "en").split("-")[0].lower()
    name = FALLBACK_AREA_NAMES.get(language, FALLBACK_AREA_NAMES["en"])
    return area_registry.async_get_or_create(name).id


@callback
def async_sync_device_areas(
    hass: HomeAssistant,
    entry_id: str,
    discovered: list[DiscoveredBatteryEntity],
) -> list[str]:
    """Put every shadow device into the room of its source entity.

    - Source has a room -> the device gets that room, even if someone set
      a different one by hand (manual rooms are intentionally overwritten).
    - Source has no room -> the device goes to the fallback area, which is
      created the first time it is needed.
    - Room overrides on the Battery Guard entities themselves are cleared
      so that the entities always follow their device.

    A brand-new device is created by the sensor platform after the first
    refresh, so it receives its room on the following refresh.
    Returns the names of the devices whose room was changed.
    """
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    area_registry = ar.async_get(hass)
    tracked = async_get_tracked_devices(hass, entry_id)

    fallback_area_id: str | None = None
    changed: list[str] = []

    for item in discovered:
        device_id = tracked.get(item.entity_id)
        if device_id is None:
            continue
        device = device_registry.async_get(device_id)
        if device is None:
            continue

        target_area_id = item.area_id
        if target_area_id is None or area_registry.async_get_area(target_area_id) is None:
            if fallback_area_id is None:
                fallback_area_id = _async_get_fallback_area_id(hass, area_registry)
            target_area_id = fallback_area_id

        if device.area_id != target_area_id:
            device_registry.async_update_device(device_id, area_id=target_area_id)
            name = device.name_by_user or device.name or item.entity_id
            changed.append(name)
            _LOGGER.debug(
                "Battery Guard: moved device '%s' to area %s", name, target_area_id
            )

        for entity in er.async_entries_for_device(
            entity_registry, device_id, include_disabled_entities=True
        ):
            if entity.platform == DOMAIN and entity.area_id is not None:
                entity_registry.async_update_entity(entity.entity_id, area_id=None)

    return changed


async def async_cleanup_stale_devices(
    hass: HomeAssistant,
    entry_id: str,
    discovered_entity_ids: set[str],
    missing_since: dict[str, datetime],
    grace: timedelta,
    now: datetime,
) -> list[str]:
    """Remove shadow devices whose source entity is gone.

    - Source missing and the device has no entities at all: removed at once.
    - Source missing for longer than `grace`: removed.

    Mutates `missing_since` in place (starts/clears timers as a source
    entity disappears or reappears) and returns the display names of the
    devices that were removed after the grace period, for notification.
    Empty devices removed at once are only logged.
    """
    tracked = async_get_tracked_devices(hass, entry_id)
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    removed: list[str] = []

    for source_entity_id in list(missing_since):
        if source_entity_id not in tracked:
            # Device already gone by some other path - drop the stale timer.
            missing_since.pop(source_entity_id, None)

    for source_entity_id, device_id in tracked.items():
        if source_entity_id in discovered_entity_ids:
            missing_since.pop(source_entity_id, None)
            continue

        device = device_registry.async_get(device_id)
        name = (device.name_by_user or device.name) if device else source_entity_id

        has_entities = bool(
            er.async_entries_for_device(
                entity_registry, device_id, include_disabled_entities=True
            )
        )
        if not has_entities:
            device_registry.async_remove_device(device_id)
            missing_since.pop(source_entity_id, None)
            _LOGGER.info(
                "Battery Guard: removed empty device '%s' (source %s missing)",
                name,
                source_entity_id,
            )
            continue

        first_missing = missing_since.setdefault(source_entity_id, now)
        if now - first_missing < grace:
            continue

        device_registry.async_remove_device(device_id)
        missing_since.pop(source_entity_id, None)
        removed.append(name)
        _LOGGER.info(
            "Battery Guard: removed stale device '%s' (source %s missing for over %s)",
            name,
            source_entity_id,
            grace,
        )

    return removed
