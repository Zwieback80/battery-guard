# Projekt: Battery Guard
# Copyright (c) 2026 Christian Brandt
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Lizenz: https://polyformproject.org/licenses/noncommercial/1.0.0
#
# Kommerzielle Nutzung ist durch diese Lizenz nicht gestattet.
# Einzelheiten und Ausnahmen ergeben sich aus dem vollständigen Lizenztext.

"""Constants for the Battery Guard integration."""
from __future__ import annotations

DOMAIN = "battery_guard"
PLATFORMS = ["sensor"]
STORE_KEY = "history_store"

MANUFACTURER = "Battery Guard"

# Identifier of the household overview device (not a monitored battery).
OVERVIEW_IDENTIFIER = "overview"

# Devices whose source entity has no room are filed under this area. It is
# created automatically the first time it is needed, named after the Home
# Assistant language (an existing area with either name is reused).
FALLBACK_AREA_NAMES = {"de": "Sonstiges", "en": "Other"}

# URL under which the integration serves its dashboard card.
CARD_URL_PATH = f"/{DOMAIN}/battery-guard-card.js"

# --- Config / Options keys ---
CONF_AUTO_DISCOVER = "auto_discover"
CONF_INCLUDED_ENTITIES = "included_entities"
CONF_EXCLUDED_ENTITIES = "excluded_entities"
CONF_WARN_THRESHOLD = "warn_threshold"
CONF_LOW_THRESHOLD = "low_threshold"
CONF_CRITICAL_THRESHOLD = "critical_threshold"
CONF_OFFLINE_HOURS = "offline_hours"
CONF_SCAN_INTERVAL_MINUTES = "scan_interval_minutes"
CONF_HISTORY_DAYS = "history_days"
CONF_FORECAST_INTERVAL_HOURS = "forecast_interval_hours"
CONF_AUTO_LOG_CHANGES = "auto_log_changes"
CONF_AUTO_LOG_JUMP_THRESHOLD = "auto_log_jump_threshold"
CONF_STALE_GRACE_HOURS = "stale_grace_hours"

# --- Defaults (from the product concept: OK >40, Watch 25-40, Low 15-25, Critical <15) ---
DEFAULT_WARN_THRESHOLD = 40
DEFAULT_LOW_THRESHOLD = 25
DEFAULT_CRITICAL_THRESHOLD = 15
DEFAULT_OFFLINE_HOURS = 48
DEFAULT_SCAN_INTERVAL_MINUTES = 5
DEFAULT_HISTORY_DAYS = 14
DEFAULT_FORECAST_INTERVAL_HOURS = 6
DEFAULT_AUTO_LOG_CHANGES = True
DEFAULT_AUTO_LOG_JUMP_THRESHOLD = 40
DEFAULT_STALE_GRACE_HOURS = 72

# --- Status levels ---
STATUS_OK = "ok"
STATUS_WATCH = "watch"
STATUS_LOW = "low"
STATUS_CRITICAL = "critical"
STATUS_OFFLINE = "offline"
STATUS_UNKNOWN = "unknown"

STATUS_ORDER = [
    STATUS_CRITICAL,
    STATUS_OFFLINE,
    STATUS_LOW,
    STATUS_WATCH,
    STATUS_OK,
    STATUS_UNKNOWN,
]

STATUS_ICONS = {
    STATUS_OK: "mdi:battery",
    STATUS_WATCH: "mdi:battery-50",
    STATUS_LOW: "mdi:battery-30",
    STATUS_CRITICAL: "mdi:battery-alert",
    STATUS_OFFLINE: "mdi:battery-unknown",
    STATUS_UNKNOWN: "mdi:battery-unknown",
}

ATTR_STATUS = "status"
ATTR_LEVEL = "battery_level"
ATTR_SOURCE_ENTITY = "source_entity"
ATTR_AREA = "area"
ATTR_LAST_SEEN = "last_seen"
ATTR_DEVICE_NAME = "device_name"
ATTR_RATE_PER_DAY = "consumption_rate_per_day"
ATTR_DAYS_REMAINING = "days_remaining"
ATTR_TREND = "trend"
ATTR_HEALTH_SCORE = "health_score"
ATTR_HEALTH_LEVEL_SCORE = "health_level_score"
ATTR_HEALTH_TREND_SCORE = "health_trend_score"
ATTR_HEALTH_RELIABILITY_SCORE = "health_reliability_score"
ATTR_BATTERY_TYPE = "battery_type"
ATTR_QUANTITY = "quantity"
ATTR_CHANGE_COUNT = "change_count"
ATTR_LAST_NOTE = "last_note"
ATTR_RECENT_CHANGES = "recent_changes"
ATTR_SHOPPING_LIST = "shopping_list"

EVENT_STATUS_CHANGED = f"{DOMAIN}_status_changed"
