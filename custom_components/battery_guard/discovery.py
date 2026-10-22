# Projekt: Battery Guard
# Copyright (c) 2026 Christian Brandt
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Lizenz: https://polyformproject.org/licenses/noncommercial/1.0.0
#
# Kommerzielle Nutzung ist durch diese Lizenz nicht gestattet.
# Einzelheiten und Ausnahmen ergeben sich aus dem vollständigen Lizenztext.

"""Auto-discovery of battery-related entities in Home Assistant.

Two families of source entities are recognised, matching what real HA
installs expose (see product research notes):

1. ``sensor`` entities with ``device_class: battery`` (or unit ``%`` and an
   entity_id/name containing "battery") -> numeric battery level in %.
2. ``binary_sensor`` entities with ``device_class: battery`` -> boolean
   "battery low" indicator only, no percentage (e.g. many smoke detectors).
"""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN


@dataclass
class DiscoveredBatteryEntity:
    """A single discovered battery source entity."""

    entity_id: str
    kind: str  # "level" (0-100 %) or "binary" (low/ok only)
    name: str
    area: str | None
    device_id: str | None
    area_id: str | None = None  # registry id of the source's area


def _resolve_name(hass: HomeAssistant, ent_entry, state: State | None) -> str:
    if ent_entry is not None and ent_entry.name:
        return ent_entry.name
    if state is not None and state.name:
        return state.name
    if ent_entry is not None and ent_entry.original_name:
        return ent_entry.original_name
    return ent_entry.entity_id if ent_entry is not None else "Unbekanntes Gerät"


def _resolve_area_id(hass: HomeAssistant, ent_entry) -> str | None:
    """Area id of the source entity (its own area first, then its device's)."""
    if ent_entry is None:
        return None
    area_id = ent_entry.area_id
    if area_id is None and ent_entry.device_id:
        dev_reg = dr.async_get(hass)
        device = dev_reg.async_get(ent_entry.device_id)
        if device is not None:
            area_id = device.area_id
    if area_id is not None and ar.async_get(hass).async_get_area(area_id) is None:
        return None  # dangling reference to a deleted area
    return area_id


def _resolve_area(hass: HomeAssistant, ent_entry) -> str | None:
    area_id = _resolve_area_id(hass, ent_entry)
    if area_id is None:
        return None
    area = ar.async_get(hass).async_get_area(area_id)
    return area.name if area else None


def async_discover_battery_entities(
    hass: HomeAssistant,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> list[DiscoveredBatteryEntity]:
    """Scan all current states for battery-related entities."""
    exclude_set = set(exclude or [])
    include_set = set(include) if include else None

    ent_reg = er.async_get(hass)
    discovered: list[DiscoveredBatteryEntity] = []

    for state in hass.states.async_all():
        entity_id = state.entity_id
        domain = entity_id.split(".", 1)[0]
        if domain not in ("sensor", "binary_sensor"):
            continue
        if entity_id in exclude_set:
            continue
        if include_set is not None and entity_id not in include_set:
            continue

        ent_entry = ent_reg.async_get(entity_id)

        # Critical: never treat our own generated sensors as a new source
        # to monitor. Without this check, a health-score/status sensor
        # (which carries "battery" in its entity_id and reports a "%"
        # unit, same as a real battery) gets rediscovered as if it were
        # a new device — and the next cycle rediscovers *that* sensor's
        # output too, compounding without bound.
        if ent_entry is not None and ent_entry.platform == DOMAIN:
            continue

        device_class = state.attributes.get("device_class")
        unit = state.attributes.get("unit_of_measurement")
        looks_like_battery_name = "battery" in entity_id.lower()

        kind: str | None = None
        if domain == "sensor":
            if device_class == "battery" or (unit == "%" and looks_like_battery_name):
                kind = "level"
        elif domain == "binary_sensor":
            if device_class == "battery" or (
                looks_like_battery_name
                and "battery_level" not in entity_id
                and "battery_state" not in entity_id
            ):
                kind = "binary"

        if kind is None:
            continue

        # Skip the auxiliary "battery_state" (charging/discharging/full)
        # sensors — they describe a mobile device's charging state, not a
        # replaceable-battery level we can act on.
        if kind == "level" and entity_id.endswith("_battery_state"):
            continue

        name = _resolve_name(hass, ent_entry, state)
        area = _resolve_area(hass, ent_entry)
        area_id = _resolve_area_id(hass, ent_entry)
        device_id = ent_entry.device_id if ent_entry else None

        discovered.append(
            DiscoveredBatteryEntity(
                entity_id=entity_id,
                kind=kind,
                name=name,
                area=area,
                device_id=device_id,
                area_id=area_id,
            )
        )

    return discovered
