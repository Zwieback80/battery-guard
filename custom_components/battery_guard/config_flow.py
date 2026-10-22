# Projekt: Battery Guard
# Copyright (c) 2026 Christian Brandt
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Lizenz: https://polyformproject.org/licenses/noncommercial/1.0.0
#
# Kommerzielle Nutzung ist durch diese Lizenz nicht gestattet.
# Einzelheiten und Ausnahmen ergeben sich aus dem vollständigen Lizenztext.

"""Config flow for Battery Guard."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_AUTO_LOG_CHANGES,
    CONF_AUTO_LOG_JUMP_THRESHOLD,
    CONF_CRITICAL_THRESHOLD,
    CONF_FORECAST_INTERVAL_HOURS,
    CONF_HISTORY_DAYS,
    CONF_LOW_THRESHOLD,
    CONF_OFFLINE_HOURS,
    CONF_SCAN_INTERVAL_MINUTES,
    CONF_STALE_GRACE_HOURS,
    CONF_WARN_THRESHOLD,
    DEFAULT_AUTO_LOG_CHANGES,
    DEFAULT_AUTO_LOG_JUMP_THRESHOLD,
    DEFAULT_CRITICAL_THRESHOLD,
    DEFAULT_FORECAST_INTERVAL_HOURS,
    DEFAULT_HISTORY_DAYS,
    DEFAULT_LOW_THRESHOLD,
    DEFAULT_OFFLINE_HOURS,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DEFAULT_STALE_GRACE_HOURS,
    DEFAULT_WARN_THRESHOLD,
    DOMAIN,
)


class BatteryGuardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup. Single instance only."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="Battery Guard", data={})

        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return BatteryGuardOptionsFlow(config_entry)


class BatteryGuardOptionsFlow(config_entries.OptionsFlow):
    """Options: thresholds, offline window, scan interval."""

    def __init__(self, config_entry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        options = self.config_entry.options or {}

        if user_input is not None:
            warn = user_input[CONF_WARN_THRESHOLD]
            low = user_input[CONF_LOW_THRESHOLD]
            critical = user_input[CONF_CRITICAL_THRESHOLD]
            if not (critical < low < warn <= 100):
                errors["base"] = "invalid_thresholds"
            else:
                return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_WARN_THRESHOLD,
                    default=options.get(CONF_WARN_THRESHOLD, DEFAULT_WARN_THRESHOLD),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
                vol.Required(
                    CONF_LOW_THRESHOLD,
                    default=options.get(CONF_LOW_THRESHOLD, DEFAULT_LOW_THRESHOLD),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
                vol.Required(
                    CONF_CRITICAL_THRESHOLD,
                    default=options.get(CONF_CRITICAL_THRESHOLD, DEFAULT_CRITICAL_THRESHOLD),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
                vol.Required(
                    CONF_OFFLINE_HOURS,
                    default=options.get(CONF_OFFLINE_HOURS, DEFAULT_OFFLINE_HOURS),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=168)),
                vol.Required(
                    CONF_SCAN_INTERVAL_MINUTES,
                    default=options.get(
                        CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
                vol.Required(
                    CONF_HISTORY_DAYS,
                    default=options.get(CONF_HISTORY_DAYS, DEFAULT_HISTORY_DAYS),
                ): vol.All(vol.Coerce(int), vol.Range(min=3, max=60)),
                vol.Required(
                    CONF_FORECAST_INTERVAL_HOURS,
                    default=options.get(
                        CONF_FORECAST_INTERVAL_HOURS, DEFAULT_FORECAST_INTERVAL_HOURS
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=48)),
                vol.Required(
                    CONF_AUTO_LOG_CHANGES,
                    default=options.get(CONF_AUTO_LOG_CHANGES, DEFAULT_AUTO_LOG_CHANGES),
                ): bool,
                vol.Required(
                    CONF_AUTO_LOG_JUMP_THRESHOLD,
                    default=options.get(
                        CONF_AUTO_LOG_JUMP_THRESHOLD, DEFAULT_AUTO_LOG_JUMP_THRESHOLD
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=90)),
                vol.Required(
                    CONF_STALE_GRACE_HOURS,
                    default=options.get(CONF_STALE_GRACE_HOURS, DEFAULT_STALE_GRACE_HOURS),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=720)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
