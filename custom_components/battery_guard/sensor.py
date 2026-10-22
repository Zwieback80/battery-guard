# Projekt: Battery Guard
# Copyright (c) 2026 Christian Brandt
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Lizenz: https://polyformproject.org/licenses/noncommercial/1.0.0
#
# Kommerzielle Nutzung ist durch diese Lizenz nicht gestattet.
# Einzelheiten und Ausnahmen ergeben sich aus dem vollständigen Lizenztext.

"""Sensor platform for Battery Guard: one entity per monitored device, plus
one overview sensor summarising the whole household."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_AREA,
    ATTR_BATTERY_TYPE,
    ATTR_CHANGE_COUNT,
    ATTR_DAYS_REMAINING,
    ATTR_HEALTH_LEVEL_SCORE,
    ATTR_HEALTH_RELIABILITY_SCORE,
    ATTR_HEALTH_TREND_SCORE,
    ATTR_LAST_NOTE,
    ATTR_LAST_SEEN,
    ATTR_LEVEL,
    ATTR_QUANTITY,
    ATTR_RATE_PER_DAY,
    ATTR_RECENT_CHANGES,
    ATTR_SHOPPING_LIST,
    ATTR_SOURCE_ENTITY,
    ATTR_STATUS,
    ATTR_TREND,
    DOMAIN,
    MANUFACTURER,
    STATUS_CRITICAL,
    STATUS_ICONS,
    STATUS_LOW,
    STATUS_OFFLINE,
    STATUS_ORDER,
    STORE_KEY,
)
from .storage import BatteryGuardHistoryStore
from .coordinator import BatteryGuardCoordinator, BatteryGuardDeviceStatus


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: BatteryGuardCoordinator = hass.data[DOMAIN][entry.entry_id]
    history_store: BatteryGuardHistoryStore = hass.data[DOMAIN][STORE_KEY]
    await coordinator.async_config_entry_first_refresh()

    known_entities: set[str] = set()

    @callback
    def _add_new_entities() -> None:
        new_entities = []
        for entity_id, status in coordinator.data.items():
            if entity_id not in known_entities:
                known_entities.add(entity_id)
                new_entities.append(BatteryGuardDeviceSensor(coordinator, entity_id))
                new_entities.append(BatteryGuardHealthScoreSensor(coordinator, entity_id))
                new_entities.append(
                    BatteryGuardChangeHistorySensor(coordinator, entity_id, history_store)
                )
                if status.kind == "level":
                    new_entities.append(BatteryGuardForecastSensor(coordinator, entity_id))
        if new_entities:
            async_add_entities(new_entities)

    _add_new_entities()
    async_add_entities([BatteryGuardOverviewSensor(coordinator, entry, history_store)])
    entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))


class BatteryGuardDeviceSensor(CoordinatorEntity[BatteryGuardCoordinator], SensorEntity):
    """Status of a single monitored battery."""

    _attr_has_entity_name = True
    _attr_translation_key = "battery_status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: BatteryGuardCoordinator, source_entity_id: str) -> None:
        super().__init__(coordinator)
        self._source_entity_id = source_entity_id
        self._attr_unique_id = f"{DOMAIN}_{source_entity_id}"

    @property
    def _status(self) -> BatteryGuardDeviceStatus | None:
        return self.coordinator.data.get(self._source_entity_id)

    @property
    def available(self) -> bool:
        return super().available and self._status is not None

    @property
    def native_value(self) -> str | None:
        status = self._status
        return status.status if status else None

    @property
    def icon(self) -> str:
        status = self._status
        return STATUS_ICONS.get(status.status, "mdi:battery-unknown") if status else "mdi:battery-unknown"

    @property
    def extra_state_attributes(self) -> dict:
        status = self._status
        if status is None:
            return {}
        return {
            ATTR_STATUS: status.status,
            ATTR_LEVEL: status.level,
            ATTR_SOURCE_ENTITY: status.entity_id,
            ATTR_AREA: status.area,
            ATTR_LAST_SEEN: status.last_seen.isoformat() if status.last_seen else None,
            ATTR_RATE_PER_DAY: status.consumption_rate_per_day,
            ATTR_DAYS_REMAINING: status.days_remaining,
            ATTR_TREND: status.trend,
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._source_entity_id)},
            name=self._status.name if self._status else self._source_entity_id,
            manufacturer=MANUFACTURER,
            model="Monitored battery",
        )


class BatteryGuardForecastSensor(CoordinatorEntity[BatteryGuardCoordinator], SensorEntity):
    """Estimated days remaining until the battery hits the critical threshold.

    Only created for percentage ('level') batteries — a binary low/ok
    sensor has no numeric trend to fit a forecast against.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "days_until_empty"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:calendar-clock"
    _attr_native_unit_of_measurement = "d"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: BatteryGuardCoordinator, source_entity_id: str) -> None:
        super().__init__(coordinator)
        self._source_entity_id = source_entity_id
        self._attr_unique_id = f"{DOMAIN}_{source_entity_id}_forecast"

    @property
    def _status(self) -> BatteryGuardDeviceStatus | None:
        return self.coordinator.data.get(self._source_entity_id)

    @property
    def available(self) -> bool:
        return super().available and self._status is not None

    @property
    def native_value(self) -> float | None:
        status = self._status
        return status.days_remaining if status else None

    @property
    def extra_state_attributes(self) -> dict:
        status = self._status
        if status is None:
            return {}
        return {
            ATTR_RATE_PER_DAY: status.consumption_rate_per_day,
            ATTR_TREND: status.trend,
            ATTR_SOURCE_ENTITY: status.entity_id,
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._source_entity_id)},
            name=self._status.name if self._status else self._source_entity_id,
            manufacturer=MANUFACTURER,
            model="Monitored battery",
        )


class BatteryGuardHealthScoreSensor(CoordinatorEntity[BatteryGuardCoordinator], SensorEntity):
    """0-100 health score combining level, trend, and reliability.

    Created for every monitored device (percentage and binary alike) —
    unlike the forecast sensor, a meaningful score exists even without
    a numeric trend.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "health_score"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:heart-pulse"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: BatteryGuardCoordinator, source_entity_id: str) -> None:
        super().__init__(coordinator)
        self._source_entity_id = source_entity_id
        self._attr_unique_id = f"{DOMAIN}_{source_entity_id}_health_score"

    @property
    def _status(self) -> BatteryGuardDeviceStatus | None:
        return self.coordinator.data.get(self._source_entity_id)

    @property
    def available(self) -> bool:
        status = self._status
        return super().available and status is not None and status.health_score is not None

    @property
    def native_value(self) -> int | None:
        status = self._status
        return status.health_score if status else None

    @property
    def extra_state_attributes(self) -> dict:
        status = self._status
        if status is None:
            return {}
        return {
            ATTR_HEALTH_LEVEL_SCORE: status.health_level_score,
            ATTR_HEALTH_TREND_SCORE: status.health_trend_score,
            ATTR_HEALTH_RELIABILITY_SCORE: status.health_reliability_score,
            ATTR_SOURCE_ENTITY: status.entity_id,
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._source_entity_id)},
            name=self._status.name if self._status else self._source_entity_id,
            manufacturer=MANUFACTURER,
            model="Monitored battery",
        )


class BatteryGuardChangeHistorySensor(CoordinatorEntity[BatteryGuardCoordinator], SensorEntity):
    """Date of the last logged battery change for a device.

    Populated via the battery_guard.log_change service. Shows "unbekannt"
    (no state, i.e. None) until the first change is ever logged — Battery
    Guard has no way to know a device's change history before it starts
    watching it.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "last_battery_change"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:battery-sync"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: BatteryGuardCoordinator,
        source_entity_id: str,
        history_store: BatteryGuardHistoryStore,
    ) -> None:
        super().__init__(coordinator)
        self._source_entity_id = source_entity_id
        self._history_store = history_store
        self._attr_unique_id = f"{DOMAIN}_{source_entity_id}_change_history"

    @property
    def _status(self) -> BatteryGuardDeviceStatus | None:
        return self.coordinator.data.get(self._source_entity_id)

    @property
    def available(self) -> bool:
        return super().available and self._status is not None

    @property
    def _history(self) -> dict:
        return self._history_store.get_device_history(self._source_entity_id)

    @property
    def native_value(self):
        changes = self._history["changes"]
        if not changes:
            return None
        return dt_util.parse_datetime(changes[-1]["date"])

    @property
    def extra_state_attributes(self) -> dict:
        history = self._history
        changes = history["changes"]
        last_note = changes[-1].get("note") if changes else None
        return {
            ATTR_BATTERY_TYPE: history.get("battery_type"),
            ATTR_QUANTITY: history.get("quantity", 1),
            ATTR_CHANGE_COUNT: len(changes),
            ATTR_LAST_NOTE: last_note,
            ATTR_RECENT_CHANGES: list(reversed(changes[-5:])),
            ATTR_SOURCE_ENTITY: self._source_entity_id,
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._source_entity_id)},
            name=self._status.name if self._status else self._source_entity_id,
            manufacturer=MANUFACTURER,
            model="Monitored battery",
        )


class BatteryGuardOverviewSensor(CoordinatorEntity[BatteryGuardCoordinator], SensorEntity):
    """Household-wide summary: worst status + counts per level."""

    _attr_has_entity_name = True
    _attr_translation_key = "overview"
    _attr_icon = "mdi:battery-heart-variant"

    def __init__(
        self,
        coordinator: BatteryGuardCoordinator,
        entry: ConfigEntry,
        history_store: BatteryGuardHistoryStore,
    ) -> None:
        super().__init__(coordinator)
        self._history_store = history_store
        self._attr_unique_id = f"{DOMAIN}_overview_{entry.entry_id}"

    @property
    def native_value(self) -> str:
        statuses = [item.status for item in self.coordinator.data.values()]
        for level in STATUS_ORDER:
            if level in statuses:
                return level
        return "unknown"

    @property
    def extra_state_attributes(self) -> dict:
        items = list(self.coordinator.data.values())
        counts = {level: 0 for level in STATUS_ORDER}
        for item in items:
            counts[item.status] = counts.get(item.status, 0) + 1

        attention_needed = [
            item.name
            for item in items
            if item.status in (STATUS_CRITICAL, STATUS_LOW, STATUS_OFFLINE)
        ]

        scored = [item.health_score for item in items if item.health_score is not None]
        average_health_score = round(sum(scored) / len(scored)) if scored else None

        shopping_list: dict[str, int] = {}
        unknown_type = (
            "unbekannter Typ"
            if self.hass and (self.hass.config.language or "").startswith("de")
            else "unknown type"
        )
        for item in items:
            if item.status not in (STATUS_CRITICAL, STATUS_LOW):
                continue
            history = self._history_store.get_device_history(item.entity_id)
            battery_type = history.get("battery_type")
            quantity = history.get("quantity", 1)
            key = battery_type or unknown_type
            shopping_list[key] = shopping_list.get(key, 0) + quantity

        return {
            "monitored_devices": len(items),
            "counts": counts,
            "needs_attention": attention_needed,
            "average_health_score": average_health_score,
            ATTR_SHOPPING_LIST: shopping_list,
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, "overview")},
            name="Battery Guard",
            manufacturer=MANUFACTURER,
            model="Overview",
        )
