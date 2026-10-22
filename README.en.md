# Battery Guard

[🇩🇪 Deutsch](README.md) · 🇬🇧 English

Battery Guard is a Home Assistant integration that **finds every battery in your smart home automatically**, rates its condition, forecasts consumption and tells you **which battery needs replacing and when**. There is nothing to configure: install, add, done.

- Tested with Home Assistant 2026.9.x
- Install via HACS (custom repository) or manually
- License: [PolyForm Noncommercial 1.0.0](LICENSE) – **commercial use is not permitted**

## Features

### Automatic discovery
Battery Guard scans all entities and finds batteries on its own:
- `sensor` with device class *battery* (or unit `%` and "battery" in the name) → battery with a percentage
- `binary_sensor` with device class *battery* → "battery low" yes/no only (e.g. many smoke detectors)
- Helper sensors such as `…_battery_state` (charging/discharging) and Battery Guard's own sensors are ignored.

New devices are picked up on the next refresh (every 5 minutes by default).

### Status
Every device gets a status:

| Status | Meaning (defaults) |
|---|---|
| `ok` | 40 % and above |
| `watch` | 25 – 40 % |
| `low` | 15 – 25 % |
| `critical` | below 15 % – for batteries without a percentage: "battery low" is active |
| `offline` | the device has not reported for more than 48 hours |
| `unknown` | value cannot be read |

All thresholds and the offline time can be changed in the options.

### Forecast: "days until empty"
From the history of the last days (default: 14) Battery Guard computes the drain in %/day with a least-squares line and estimates how many days remain until the critical threshold. If the level does not fall, the trend is *stable* or *rising*. The forecast is recomputed every 6 hours and needs at least 3 data points; until then the trend is *unknown*.

### Health score (0–100)
One number per device, deliberately transparent, built from three sub-scores:
- **Level (50 %)** – where the value sits between the critical threshold and full
- **Trend (30 %)** – days of runway relative to 60 days (neutral 70 without trend data)
- **Reliability (20 %)** – 0 if the device is offline, otherwise 100

The sub-scores are exposed as attributes, so an odd-looking score can be explained.

### Battery changes and battery type
- **Automatic detection:** if the level jumps up by at least 40 percentage points, Battery Guard logs a change on its own. Devices that also expose a charging-state sensor (phone, tablet) are excluded, since a jump there is just charging.
- **Manual:** the `battery_guard.log_change` action (see below).
- Up to 20 changes per device are stored (type, quantity, note). The data lives in Home Assistant's `.storage` and is never purged by the recorder.

### Shopping list
The overview sensor adds up, for all devices with status *low* or *critical*, which batteries you need (type × quantity), e.g. `AAA: 3`. Set the type with `battery_guard.set_battery_info` or when logging a change.

### Rooms – fully automatic
Every Battery Guard device is placed in the **room of its source** automatically. If the source has no room, it goes to the area **"Other"** (**"Sonstiges"** if Home Assistant is set to German; created on demand). Rooms set by hand on a Battery Guard device are deliberately overwritten: to move a device, change the room of the source device.

### Automatic cleanup
When a device is replaced or a source entity is renamed, a ghost device would otherwise remain. Battery Guard removes devices whose source has been missing for more than **72 hours** and shows a notification. Devices without any entities are removed immediately. The grace period survives restarts and can be changed in the options (0 = cleanup off).

## Entities

Per monitored battery (all in the *diagnostic* category):

| Entity | Content |
|---|---|
| Batteriestatus (battery status) | status, level, source, room, last seen, drain/day, days remaining, trend |
| Health Score | 0–100 with sub-scores |
| Tage bis leer (days until empty) | only for batteries with a percentage |
| Letzter Batteriewechsel (last change) | timestamp; attributes: battery type, quantity, change count, last note, recent changes |

Plus a device **Battery Guard** with the sensor **Übersicht** (overview): state = worst status in the household; attributes: `monitored_devices`, `counts`, `needs_attention`, `average_health_score`, `shopping_list`.

## Actions

| Action | Purpose |
|---|---|
| `battery_guard.log_change` | log a battery change (device, optional type, quantity, note, date) |
| `battery_guard.set_battery_info` | store battery type and quantity without logging a change |
| `battery_guard.clear_history` | delete a device's change history (e.g. test entries) |

## Options

Settings → Devices & services → Battery Guard → Configure:

| Option | Default |
|---|---|
| Watch from / Low from / Critical from | 40 / 25 / 15 % |
| Offline after | 48 hours |
| Refresh interval | 5 minutes |
| History window for the forecast | 14 days |
| Recompute forecast every | 6 hours |
| Detect battery changes automatically | on |
| Jump threshold for that | 40 percentage points |
| Grace period for orphaned devices | 72 hours (0 = off) |

## Dashboard card

Battery Guard ships with its **own card**. It needs no other cards or extensions and loads together with the integration – no resource has to be set up.

Add it: edit dashboard → *Add card* → **Battery Guard**, or in YAML:

```yaml
type: custom:battery-guard-card
```

The card shows:
- counters per status (critical, low, watch, offline, ok) and the average health score
- all batteries **grouped by room** (the fallback area last), critical devices first
- per device level, days until empty and health score; tapping a row expands the details (trend, drain, last change, battery type)
- in the details: **"Battery replaced"** and **"Save type"** straight from the dashboard
- the shopping list

Options (all optional):

| Option | Default | Meaning |
|---|---|---|
| `title` | "Battery Guard" | card title |
| `show_overview` | `true` | show the counters per status |
| `show_shopping_list` | `true` | show the shopping list |
| `hide_ok` | `false` | hide devices with status *ok* and show only what needs attention |

The card finds new devices on its own and follows Home Assistant's language (German or English). After updating the integration, clear the browser cache if the card still looks old.

## Installation

**HACS (recommended)**
1. HACS → ⋮ → *Custom repositories* → add `https://github.com/Zwieback80/battery-guard` as *Integration*.
2. Install *Battery Guard* and restart Home Assistant.
3. Settings → Devices & services → *Add integration* → **Battery Guard**.

**Manual:** copy the folder `custom_components/battery_guard` to `config/custom_components/`, restart, add the integration.

Only one instance is allowed.

## Languages
The integration and the card are available in **German and English** and follow Home Assistant's language; other languages fall back to English.

## License and terms of use
Battery Guard is licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE). You may use, modify and share it privately and for other non-commercial purposes. **Commercial use is not permitted.** The full license text in the file `LICENSE` is authoritative; see also `NOTICE`.

Copyright (c) 2026 Christian Brandt · christianbrandt@mailbox.org
