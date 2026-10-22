# Projekt: Battery Guard
# Copyright (c) 2026 Christian Brandt
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Lizenz: https://polyformproject.org/licenses/noncommercial/1.0.0
#
# Kommerzielle Nutzung ist durch diese Lizenz nicht gestattet.
# Einzelheiten und Ausnahmen ergeben sich aus dem vollständigen Lizenztext.

"""The Battery Guard integration."""
from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util

from .const import CARD_URL_PATH, DOMAIN, PLATFORMS, STORE_KEY
from .coordinator import BatteryGuardCoordinator
from .storage import BatteryGuardHistoryStore

_LOGGER = logging.getLogger(__name__)

SERVICE_LOG_CHANGE = "log_change"
SERVICE_CLEAR_HISTORY = "clear_history"
SERVICE_SET_BATTERY_INFO = "set_battery_info"

SERVICE_LOG_CHANGE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Optional("battery_type"): cv.string,
        vol.Optional("quantity"): vol.Any(None, str, int, float),
        vol.Optional("note"): cv.string,
        vol.Optional("date"): cv.date,
    }
)

SERVICE_CLEAR_HISTORY_SCHEMA = vol.Schema({vol.Required("device_id"): cv.string})

SERVICE_SET_BATTERY_INFO_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): cv.string,
        vol.Required("battery_type"): cv.string,
        vol.Optional("quantity"): vol.Any(None, str, int, float),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    if STORE_KEY not in hass.data[DOMAIN]:
        store = BatteryGuardHistoryStore(hass)
        await store.async_load()
        hass.data[DOMAIN][STORE_KEY] = store
        _async_register_services(hass)
        await _async_register_card(hass)

    coordinator = BatteryGuardCoordinator(hass, entry, hass.data[DOMAIN][STORE_KEY])
    hass.data[DOMAIN][entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the dashboard card and load it in the frontend.

    No manual dashboard resource is needed: once the integration is set up,
    ``type: custom:battery-guard-card`` works in every dashboard.
    """
    try:
        card_file = Path(__file__).parent / "frontend" / "battery-guard-card.js"
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL_PATH, str(card_file), False)]
        )
        integration = await async_get_integration(hass, DOMAIN)
        add_extra_js_url(hass, f"{CARD_URL_PATH}?v={integration.version}")
    except Exception:  # noqa: BLE001 - the card is optional, never block setup
        _LOGGER.warning(
            "Battery Guard: could not register the dashboard card", exc_info=True
        )


def _async_register_services(hass: HomeAssistant) -> None:
    dev_reg = dr.async_get(hass)

    def _resolve_source_entity(device_id: str) -> str:
        device = dev_reg.async_get(device_id)
        if device is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unknown_device",
                translation_placeholders={"device_id": device_id},
            )
        source_entity_id = next(
            (identifier for domain, identifier in device.identifiers if domain == DOMAIN),
            None,
        )
        if source_entity_id is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="not_battery_guard_device"
            )
        return source_entity_id

    async def _async_refresh_all_coordinators() -> None:
        for value in hass.data[DOMAIN].values():
            if isinstance(value, BatteryGuardCoordinator):
                await value.async_request_refresh()

    def _parse_quantity(raw) -> int | None:
        """Best-effort int conversion — bad/missing input just means
        "don't change the quantity" rather than failing the whole call."""
        if raw in (None, ""):
            return None
        try:
            value = int(float(raw))
        except (TypeError, ValueError):
            return None
        return max(1, min(20, value))

    async def _handle_log_change(call: ServiceCall) -> None:
        source_entity_id = _resolve_source_entity(call.data["device_id"])
        store: BatteryGuardHistoryStore = hass.data[DOMAIN][STORE_KEY]
        date_val = call.data.get("date")
        when = dt_util.start_of_local_day(date_val) if date_val else None
        await store.async_log_change(
            source_entity_id,
            call.data.get("battery_type"),
            call.data.get("note"),
            when=when,
            quantity=_parse_quantity(call.data.get("quantity")),
        )
        await _async_refresh_all_coordinators()

    async def _handle_clear_history(call: ServiceCall) -> None:
        source_entity_id = _resolve_source_entity(call.data["device_id"])
        store: BatteryGuardHistoryStore = hass.data[DOMAIN][STORE_KEY]
        cleared = await store.async_clear_history(source_entity_id)
        if not cleared:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="no_history"
            )
        await _async_refresh_all_coordinators()

    async def _handle_set_battery_info(call: ServiceCall) -> None:
        source_entity_id = _resolve_source_entity(call.data["device_id"])
        store: BatteryGuardHistoryStore = hass.data[DOMAIN][STORE_KEY]
        await store.async_set_battery_info(
            source_entity_id,
            call.data["battery_type"],
            _parse_quantity(call.data.get("quantity")),
        )
        await _async_refresh_all_coordinators()

    hass.services.async_register(
        DOMAIN, SERVICE_LOG_CHANGE, _handle_log_change, schema=SERVICE_LOG_CHANGE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_HISTORY,
        _handle_clear_history,
        schema=SERVICE_CLEAR_HISTORY_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_BATTERY_INFO,
        _handle_set_battery_info,
        schema=SERVICE_SET_BATTERY_INFO_SCHEMA,
    )


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options (thresholds etc.) change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Löschen eines Geräts nur erlauben, wenn es keine Entitäten mehr hat.

    Aktiv überwachte Geräte (mit Entitäten) bleiben dadurch geschützt;
    verwaiste Duplikate können über die UI oder API entfernt werden.
    """
    ent_reg = er.async_get(hass)
    entities = er.async_entries_for_device(
        ent_reg, device_entry.id, include_disabled_entities=True
    )
    return not entities


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
