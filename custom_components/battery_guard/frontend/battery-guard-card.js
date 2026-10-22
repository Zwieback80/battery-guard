/*
 * Projekt: Battery Guard
 * Copyright (c) 2026 Christian Brandt
 * SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
 * Lizenz: https://polyformproject.org/licenses/noncommercial/1.0.0
 *
 * Kommerzielle Nutzung ist durch diese Lizenz nicht gestattet.
 * Einzelheiten und Ausnahmen ergeben sich aus dem vollständigen Lizenztext.
 *
 * battery-guard-card: self-contained dashboard card, no dependencies.
 * Usage:  type: custom:battery-guard-card
 * Options: title, show_overview (true), show_shopping_list (true), hide_ok (false)
 */
(() => {
  const I18N = {
    de: {
      title: "Battery Guard", critical: "Kritisch", low: "Niedrig", watch: "Beobachten",
      offline: "Offline", ok: "OK", unknown: "Unbekannt", fallback: "Sonstiges",
      none: "Keine Batteriegeräte gefunden. Ist die Integration Battery Guard eingerichtet?",
      level: "Füllstand", days: "Tage bis leer", trend: "Trend", rate: "Verbrauch",
      lastSeen: "Zuletzt gemeldet", health: "Health Score", lastChange: "Letzter Wechsel",
      type: "Batterietyp", qty: "Anzahl", never: "nie erfasst", more: "Details öffnen",
      changed: "Batterie gewechselt", saveType: "Typ speichern", shopping: "Einkaufsliste",
      avg: "Ø Health", attention: "Alles in Ordnung", typePh: "z. B. AAA", done: "Gespeichert",
      falling: "fallend", stable: "stabil", rising: "steigend", trend_unknown: "unbekannt",
      perDay: "%/Tag", needType: "Bitte zuerst einen Batterietyp eingeben.",
    },
    en: {
      title: "Battery Guard", critical: "Critical", low: "Low", watch: "Watch",
      offline: "Offline", ok: "OK", unknown: "Unknown", fallback: "Other",
      none: "No battery devices found. Is the Battery Guard integration set up?",
      level: "Level", days: "Days until empty", trend: "Trend", rate: "Drain",
      lastSeen: "Last reported", health: "Health score", lastChange: "Last change",
      type: "Battery type", qty: "Quantity", never: "never logged", more: "Open details",
      changed: "Battery replaced", saveType: "Save type", shopping: "Shopping list",
      avg: "Avg health", attention: "All good", typePh: "e.g. AAA", done: "Saved",
      falling: "falling", stable: "stable", rising: "rising", trend_unknown: "unknown",
      perDay: "%/day", needType: "Please enter a battery type first.",
    },
  };
  const ORDER = ["critical", "offline", "low", "watch", "ok", "unknown"];
  const COLORS = {
    critical: "var(--error-color, #db4437)",
    offline: "var(--disabled-text-color, #9e9e9e)",
    low: "#fb8c00",
    watch: "var(--warning-color, #ffa600)",
    ok: "var(--success-color, #43a047)",
    unknown: "var(--disabled-text-color, #9e9e9e)",
  };
  const FALLBACK_NAMES = ["sonstiges", "other"];

  const esc = (v) =>
    String(v === null || v === undefined ? "" : v).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const cleanName = (name) =>
    String(name || "")
      .replace(/\s+(batteriestatus|battery status)$/i, "")
      .replace(/\s+(battery( level| status)?|batterie|batteriestatus)$/i, "")
      .replace(/\s+/g, " ")
      .trim();

  class BatteryGuardCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._expanded = new Set();
      this._config = {};
      this._sig = "";
      this._msg = "";
      this._pending = false;
      this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
      this.shadowRoot.addEventListener("focusout", () => setTimeout(() => this._afterBlur(), 0));
    }

    setConfig(config) {
      this._config = Object.assign(
        { show_overview: true, show_shopping_list: true, hide_ok: false }, config || {});
      this._sig = "";
      if (this._hass) this.hass = this._hass;
    }

    set hass(hass) {
      this._hass = hass;
      const data = this._collect();
      const sig = JSON.stringify([data.devices, data.shopping, hass.language, this._config,
        [...this._expanded], this._msg]);
      if (sig === this._sig) return;
      if (this._isEditing()) { this._pending = true; return; }
      this._sig = sig;
      this._data = data;
      this._render();
    }

    getCardSize() {
      return 2 + (this._data ? this._data.devices.length : 4);
    }

    static getStubConfig() { return {}; }

    _t(key) {
      const lang = ((this._hass && this._hass.language) || "en").toLowerCase();
      return (I18N[lang.startsWith("de") ? "de" : "en"])[key] || key;
    }

    _isEditing() {
      const el = this.shadowRoot.activeElement;
      return !!el && el.tagName === "INPUT";
    }

    _afterBlur() {
      if (this._pending && !this._isEditing()) {
        this._pending = false;
        this._sig = "";
        if (this._hass) this.hass = this._hass;
      }
    }

    _collect() {
      const hass = this._hass;
      const states = hass.states || {};
      const groups = {};
      let shopping = {};
      for (const id of Object.keys(states)) {
        if (!id.startsWith("sensor.")) continue;
        const st = states[id];
        const a = st.attributes || {};
        if (a.monitored_devices !== undefined && a.counts !== undefined) {
          shopping = a.shopping_list || {};
          continue;
        }
        const src = a.source_entity;
        if (!src) continue;
        const g = groups[src] || (groups[src] = { source: src });
        if (a.status !== undefined) { g.status = st; g.statusId = id; }
        else if (a.health_level_score !== undefined) { g.health = st; }
        else if (a.change_count !== undefined) { g.history = st; }
      }

      const devices = [];
      for (const src of Object.keys(groups)) {
        const g = groups[src];
        if (!g.status) continue;
        const a = g.status.attributes;
        const ent = hass.entities && hass.entities[g.statusId];
        const deviceId = ent && ent.device_id ? ent.device_id : null;
        const dev = deviceId && hass.devices ? hass.devices[deviceId] : null;
        const rawName = (dev && (dev.name_by_user || dev.name)) || a.friendly_name || src;
        const area = a.area && !FALLBACK_NAMES.includes(String(a.area).toLowerCase()) ? a.area : "";
        const h = g.health ? g.health.attributes : {};
        const hs = g.health && !isNaN(Number(g.health.state)) ? Number(g.health.state) : null;
        const ha = g.history ? g.history.attributes : {};
        devices.push({
          source: src, statusId: g.statusId, deviceId,
          name: cleanName(rawName) || src,
          area, status: ORDER.includes(g.status.state) ? g.status.state : "unknown",
          level: typeof a.battery_level === "number" ? a.battery_level : null,
          days: typeof a.days_remaining === "number" ? a.days_remaining : null,
          rate: typeof a.consumption_rate_per_day === "number" ? a.consumption_rate_per_day : null,
          trend: a.trend || "unknown", lastSeen: a.last_seen || null,
          health: hs,
          sub: [h.health_level_score, h.health_trend_score, h.health_reliability_score],
          lastChange: g.history && !["unknown", "unavailable"].includes(g.history.state)
            ? g.history.state : null,
          type: ha.battery_type || "", qty: ha.quantity || 1, changes: ha.change_count || 0,
        });
      }
      return { devices, shopping };
    }

    _fmtDate(iso, withTime) {
      if (!iso) return "";
      const d = new Date(iso);
      if (isNaN(d)) return "";
      const lang = (this._hass && this._hass.language) || "en";
      return withTime ? d.toLocaleString(lang) : d.toLocaleDateString(lang);
    }

    _render() {
      const cfg = this._config;
      const all = this._data.devices;
      const counts = {};
      ORDER.forEach((k) => (counts[k] = 0));
      all.forEach((d) => counts[d.status]++);
      const scored = all.filter((d) => d.health !== null).map((d) => d.health);
      const avg = scored.length ? Math.round(scored.reduce((x, y) => x + y, 0) / scored.length) : null;

      const visible = all.filter((d) => !(cfg.hide_ok && d.status === "ok"));
      const byArea = {};
      visible.forEach((d) => (byArea[d.area] = byArea[d.area] || []).push(d));
      const areaNames = Object.keys(byArea).sort((a, b) => {
        if (a === "") return 1;
        if (b === "") return -1;
        return a.localeCompare(b);
      });
      const sev = (s) => ORDER.indexOf(s);

      let html = `<style>
        ha-card{padding:16px}
        .head{display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin-bottom:8px}
        .title{font-size:1.2em;font-weight:500}
        .avg{color:var(--secondary-text-color);font-size:.85em}
        .chips{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 8px}
        .chip{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:12px;
          font-size:.8em;border:1px solid var(--divider-color);color:var(--primary-text-color)}
        .chip b{font-weight:600}
        .dot{width:10px;height:10px;border-radius:50%;flex:none;display:inline-block}
        .area{margin:14px 0 4px;font-size:.8em;font-weight:600;letter-spacing:.06em;
          text-transform:uppercase;color:var(--secondary-text-color)}
        .row{display:flex;align-items:center;gap:10px;padding:8px 4px;cursor:pointer;
          border-radius:8px}
        .row:hover{background:var(--secondary-background-color)}
        .name{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
        .meta{color:var(--secondary-text-color);font-size:.85em;white-space:nowrap}
        .chev{color:var(--secondary-text-color);width:14px;text-align:center}
        .details{margin:0 4px 8px 24px;padding:10px 12px;border-radius:8px;
          background:var(--secondary-background-color);font-size:.9em}
        .kv{display:grid;grid-template-columns:auto 1fr;gap:4px 14px}
        .kv span:nth-child(odd){color:var(--secondary-text-color)}
        .actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px;align-items:center}
        input{background:var(--card-background-color);color:var(--primary-text-color);
          border:1px solid var(--divider-color);border-radius:6px;padding:6px 8px;
          font:inherit;min-width:0}
        input.t{width:110px} input.q{width:56px}
        button{font:inherit;cursor:pointer;border-radius:6px;padding:6px 10px;
          border:1px solid var(--primary-color);background:transparent;color:var(--primary-color)}
        button:hover{background:var(--primary-color);color:var(--text-primary-color,#fff)}
        .shop{margin-top:10px;font-size:.9em;color:var(--secondary-text-color)}
        .msg{margin-top:8px;font-size:.85em;color:var(--primary-color)}
        .empty{padding:12px 4px;color:var(--secondary-text-color)}
      </style>`;

      html += `<div class="head"><div class="title">${esc(cfg.title || this._t("title"))}</div>`;
      html += avg !== null ? `<div class="avg">${esc(this._t("avg"))} ${avg}</div>` : "";
      html += `</div>`;

      if (cfg.show_overview !== false && all.length) {
        html += `<div class="chips">`;
        ["critical", "low", "watch", "offline", "ok"].forEach((k) => {
          if (k === "ok" || counts[k] > 0) {
            html += `<span class="chip"><span class="dot" style="background:${COLORS[k]}"></span>
              ${esc(this._t(k))} <b>${counts[k]}</b></span>`;
          }
        });
        html += `</div>`;
      }

      if (!all.length) {
        html += `<div class="empty">${esc(this._t("none"))}</div>`;
      }

      areaNames.forEach((area) => {
        const label = area === "" ? this._t("fallback") : area;
        html += `<div class="area">${esc(label)}</div>`;
        byArea[area]
          .sort((a, b) => sev(a.status) - sev(b.status) || a.name.localeCompare(b.name))
          .forEach((d) => { html += this._rowHtml(d); });
      });

      const shop = Object.entries(this._data.shopping || {});
      if (cfg.show_shopping_list !== false && shop.length) {
        html += `<div class="shop">🛒 ${esc(this._t("shopping"))}: ${
          shop.map(([k, v]) => `${esc(k)} ×${esc(v)}`).join(", ")}</div>`;
      }
      if (this._msg) html += `<div class="msg">${esc(this._msg)}</div>`;

      this.shadowRoot.innerHTML = `<ha-card>${html}</ha-card>`;
    }

    _rowHtml(d) {
      const open = this._expanded.has(d.source);
      const parts = [];
      if (d.level !== null) parts.push(`${Math.round(d.level)} %`);
      else parts.push(esc(this._t(d.status)));
      if (d.days !== null) parts.push(`${d.days} d`);
      if (d.health !== null) parts.push(`♥ ${d.health}`);
      let html = `<div class="row" data-action="toggle" data-id="${esc(d.source)}">
        <span class="dot" style="background:${COLORS[d.status]}"></span>
        <span class="name">${esc(d.name)}</span>
        <span class="meta">${parts.join(" · ")}</span>
        <span class="chev">${open ? "▾" : "▸"}</span></div>`;
      if (!open) return html;

      const trend = this._t(d.trend === "unknown" ? "trend_unknown" : d.trend);
      html += `<div class="details"><div class="kv">
        <span>${esc(this._t("level"))}</span><span>${d.level !== null ? Math.round(d.level) + " %" : esc(this._t(d.status))}</span>
        <span>${esc(this._t("days"))}</span><span>${d.days !== null ? d.days : "–"}</span>
        <span>${esc(this._t("trend"))}</span><span>${esc(trend)}${d.rate !== null ? " (" + d.rate + " " + esc(this._t("perDay")) + ")" : ""}</span>
        <span>${esc(this._t("health"))}</span><span>${d.health !== null ? d.health + " / 100" : "–"}${
          d.sub.every((x) => x !== undefined) ? " (" + d.sub.join(" / ") + ")" : ""}</span>
        <span>${esc(this._t("lastSeen"))}</span><span>${esc(this._fmtDate(d.lastSeen, true)) || "–"}</span>
        <span>${esc(this._t("lastChange"))}</span><span>${d.lastChange ? esc(this._fmtDate(d.lastChange)) : esc(this._t("never"))}</span>
        <span>${esc(this._t("type"))}</span><span>${esc(d.type) || "–"}${d.type ? " × " + esc(d.qty) : ""}</span>
      </div>`;
      html += `<div class="actions">`;
      if (d.deviceId) {
        html += `<input class="t" data-input="type" data-id="${esc(d.source)}" placeholder="${esc(this._t("typePh"))}" value="${esc(d.type)}">
          <input class="q" data-input="qty" data-id="${esc(d.source)}" type="number" min="1" max="20" value="${esc(d.qty)}">
          <button data-action="changed" data-id="${esc(d.source)}">${esc(this._t("changed"))}</button>
          <button data-action="saveType" data-id="${esc(d.source)}">${esc(this._t("saveType"))}</button>`;
      }
      html += `<button data-action="more" data-id="${esc(d.source)}">${esc(this._t("more"))}</button>`;
      html += `</div></div>`;
      return html;
    }

    _device(source) {
      return this._data && this._data.devices.find((d) => d.source === source);
    }

    _flash(text) {
      this._msg = text;
      this._sig = "";
      if (this._hass) this.hass = this._hass;
      clearTimeout(this._flashTimer);
      this._flashTimer = setTimeout(() => {
        this._msg = "";
        this._sig = "";
        if (this._hass) this.hass = this._hass;
      }, 3500);
    }

    _onClick(ev) {
      const el = ev.composedPath().find((n) => n.dataset && n.dataset.action);
      if (!el) return;
      const source = el.dataset.id;
      const action = el.dataset.action;
      const d = this._device(source);
      if (!d) return;

      if (action === "toggle") {
        if (this._expanded.has(source)) this._expanded.delete(source);
        else this._expanded.add(source);
        this._sig = "";
        this.hass = this._hass;
        return;
      }
      if (action === "more") {
        this.dispatchEvent(new CustomEvent("hass-more-info",
          { detail: { entityId: d.statusId }, bubbles: true, composed: true }));
        return;
      }
      const q = (name) => this.shadowRoot.querySelector(`[data-input="${name}"][data-id="${CSS.escape(source)}"]`);
      const type = ((q("type") || {}).value || "").trim();
      const qty = parseInt((q("qty") || {}).value, 10);
      if (action === "changed") {
        const data = { device_id: d.deviceId };
        if (type) data.battery_type = type;
        if (qty > 0) data.quantity = String(qty);
        this._hass.callService("battery_guard", "log_change", data);
        this._flash(this._t("done"));
      } else if (action === "saveType") {
        if (!type) { this._flash(this._t("needType")); return; }
        const data = { device_id: d.deviceId, battery_type: type };
        if (qty > 0) data.quantity = String(qty);
        this._hass.callService("battery_guard", "set_battery_info", data);
        this._flash(this._t("done"));
      }
    }
  }

  if (!customElements.get("battery-guard-card")) {
    customElements.define("battery-guard-card", BatteryGuardCard);
  }
  window.customCards = window.customCards || [];
  if (!window.customCards.some((c) => c.type === "battery-guard-card")) {
    window.customCards.push({
      type: "battery-guard-card",
      name: "Battery Guard",
      description: "Alle Batterien nach Raum, mit Status, Prognose und Health Score.",
    });
  }
})();
