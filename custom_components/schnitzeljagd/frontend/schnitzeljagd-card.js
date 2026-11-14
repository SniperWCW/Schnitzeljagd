/*
 * schnitzeljagd-card – Spielleitung für die Schnitzeljagd-Integration.
 *
 * Konfiguration:
 *   type: custom:schnitzeljagd-card
 *   entity: sensor.funkel_luna_fortschritt   # beliebige Entity der Jagd
 *   title: Spielleitung                      # optional
 *   show_stations: true                      # optional, Standard true
 */

(() => {
const DOMAIN = "schnitzeljagd";

const I18N = {
  de: {
    progress: "Fortschritt",
    current: "Aktuelle Station",
    running: "Spiel läuft",
    idle: "Bereit",
    treasure_locked: "Schatz gesperrt",
    treasure_open: "Schatz frei",
    control: "Bedienung",
    prepare: "Vorbereiten",
    stop: "Medien-Stopp",
    reset: "Zurücksetzen",
    release: "Schatz freigeben",
    station_select: "Station wählen",
    start: "Starten",
    done: "Erledigt",
    open: "Offen",
    other_tasks: "Weitere Aufgaben",
    confirm_reset: "Spiel wirklich zurücksetzen? Alle Haken werden gelöscht.",
    confirm_release: "Schatz wirklich manuell freigeben?",
    confirm_undo: "Haken zurücknehmen? Es werden keine Aktionen ausgeführt.",
    missing: "Entity nicht gefunden oder keiner Schnitzeljagd zugeordnet.",
    pick: "Wähle eine Entity der Schnitzeljagd",
    entity: "Entity der Schnitzeljagd",
    title: "Titel",
    show_stations: "Stationen anzeigen",
  },
  en: {
    progress: "Progress",
    current: "Current station",
    running: "Game running",
    idle: "Ready",
    treasure_locked: "Treasure locked",
    treasure_open: "Treasure released",
    control: "Controls",
    prepare: "Prepare",
    stop: "Stop media",
    reset: "Reset",
    release: "Release treasure",
    station_select: "Choose station",
    start: "Start",
    done: "Done",
    open: "Open",
    other_tasks: "Other tasks",
    confirm_reset: "Really reset the game? All checkmarks will be cleared.",
    confirm_release: "Really release the treasure manually?",
    confirm_undo: "Undo checkmark? No actions will run.",
    missing: "Entity not found or not part of a scavenger hunt.",
    pick: "Pick an entity of the hunt",
    entity: "Hunt entity",
    title: "Title",
    show_stations: "Show stations",
  },
};

const t = (hass, key) => {
  const lang = (hass && (hass.locale?.language || hass.language) || "en").slice(0, 2);
  return (I18N[lang] || I18N.en)[key] ?? I18N.en[key] ?? key;
};

/**
 * Sammelt alle Entities der Jagd (gleiches Gerät, Plattform "schnitzeljagd")
 * und ordnet sie nach Rolle. Reine Funktion, daher testbar.
 */
function buildModel(hass, entityId) {
  const reg = hass.entities?.[entityId];
  if (!reg || reg.platform !== DOMAIN || !reg.device_id) return null;

  const model = {
    controls: {},
    stations: [],
    tasks: [],
    select: null,
    progress: null,
    current: null,
    running: null,
    treasure: null,
  };

  const stationMap = new Map();
  const ensureStation = (id, name) => {
    if (!stationMap.has(id)) stationMap.set(id, { id, name: name || id, order: 1e6, start: null, clips: [], tasks: [] });
    const st = stationMap.get(id);
    if (name) st.name = name;
    return st;
  };

  for (const [id, entry] of Object.entries(hass.entities)) {
    if (entry.platform !== DOMAIN || entry.device_id !== reg.device_id) continue;
    const state = hass.states[id];
    if (!state) continue;
    const domain = id.split(".")[0];
    const a = state.attributes || {};
    const key = entry.translation_key;

    if (domain === "sensor" && key === "progress") model.progress = id;
    else if (domain === "sensor" && key === "current_station") model.current = id;
    else if (domain === "binary_sensor" && key === "running") model.running = id;
    else if (domain === "binary_sensor" && key === "treasure") model.treasure = id;
    else if (domain === "select") model.select = id;
    else if (domain === "button" && key) model.controls[key] = id;
    else if (domain === "button" && a.kind === "station") {
      const st = ensureStation(String(a.station_id), a.station_name);
      st.start = id;
      st.order = a.order ?? st.order;
      st.icon = a.icon;
    } else if (domain === "button" && a.kind === "clip") {
      ensureStation(String(a.station_id)).clips.push({ id, name: a.clip_name || state.attributes.friendly_name, icon: a.icon });
    } else if (domain === "switch") {
      const task = { id, name: a.task_name || a.friendly_name, icon: a.icon, order: a.order ?? 1e6, station: a.station != null ? String(a.station) : null, description: a.description || "" };
      model.tasks.push(task);
      if (task.station) ensureStation(task.station).tasks.push(task);
    }
  }

  model.stations = [...stationMap.values()].sort((x, y) => x.order - y.order);
  for (const st of model.stations) st.tasks.sort((x, y) => x.order - y.order);
  model.tasks.sort((x, y) => x.order - y.order);
  model.unassigned = model.tasks.filter((task) => !task.station);
  return model;
}

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const STYLE = `
  :host { display: block; }
  ha-card { padding: 16px; }
  .head { display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
  .title { font-size: 1.25rem; font-weight: 500; }
  .chips { display: flex; gap: 6px; flex-wrap: wrap; }
  .chip { display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px; border-radius: 999px;
          border: 1px solid var(--divider-color); font-size: .8rem; font-weight: 500; white-space: nowrap; }
  .chip.on { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: transparent; }
  .chip.good { background: var(--success-color, #43a047); color: #fff; border-color: transparent; }
  .top { display: grid; grid-template-columns: 150px 1fr; gap: 16px; align-items: center; margin-bottom: 16px; }
  .ring { position: relative; width: 150px; height: 150px; }
  .ring svg { width: 100%; height: 100%; transform: rotate(-90deg); }
  .ring .bg { stroke: var(--divider-color); }
  .ring .fg { stroke: var(--primary-color); transition: stroke-dashoffset .4s; }
  .ring .num { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
  .ring .num b { font-size: 1.9rem; }
  .ring .num span { font-size: .75rem; color: var(--secondary-text-color); }
  .side { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
  .current { font-size: 1.05rem; font-weight: 500; }
  .label { font-size: .75rem; color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: .04em; }
  .btns { display: flex; gap: 8px; flex-wrap: wrap; }
  button { font: inherit; cursor: pointer; border-radius: 10px; border: 1px solid var(--divider-color);
           background: var(--card-background-color); color: var(--primary-text-color); padding: 8px 12px;
           display: inline-flex; align-items: center; gap: 6px; min-height: 40px; }
  button:active { transform: scale(.98); }
  button.primary { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: transparent; }
  button.danger { color: var(--error-color, #d32f2f); border-color: var(--error-color, #d32f2f); }
  select { font: inherit; padding: 8px; border-radius: 10px; border: 1px solid var(--divider-color);
           background: var(--card-background-color); color: var(--primary-text-color); min-height: 40px; max-width: 100%; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }
  .st { border: 1px solid var(--divider-color); border-radius: 12px; padding: 10px; display: flex; flex-direction: column; gap: 8px; }
  .st.cur { border-color: var(--primary-color); box-shadow: 0 0 0 1px var(--primary-color) inset; }
  .st h3 { margin: 0; font-size: 1rem; font-weight: 500; display: flex; align-items: center; gap: 8px; }
  .task { display: flex; align-items: center; gap: 10px; text-align: left; width: 100%; justify-content: flex-start; }
  .task.done { background: color-mix(in srgb, var(--success-color, #43a047) 18%, transparent); }
  .task small { display: block; color: var(--secondary-text-color); }
  .msg { padding: 8px; color: var(--secondary-text-color); }
  @media (max-width: 420px) { .top { grid-template-columns: 1fr; justify-items: center; } .side { width: 100%; } }
`;

class SchnitzeljagdCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._sig = "";
    this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
    this.shadowRoot.addEventListener("change", (ev) => this._onChange(ev));
  }

  setConfig(config) {
    if (!config || !config.entity) throw new Error("'entity' fehlt");
    this._config = { show_stations: true, ...config };
    this._sig = "";
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 8;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }

  static getConfigElement() {
    return document.createElement("schnitzeljagd-card-editor");
  }

  static getStubConfig(hass) {
    const ent = Object.entries(hass?.entities || {}).find(([, e]) => e.platform === DOMAIN && e.translation_key === "progress");
    return { entity: ent ? ent[0] : "" };
  }

  _signature(model) {
    const h = this._hass;
    const ids = [model.progress, model.current, model.running, model.treasure, model.select, ...model.tasks.map((x) => x.id)].filter(Boolean);
    const parts = ids.map((id) => `${id}=${h.states[id]?.state}`);
    return `${h.language}|${this._config.title}|${this._config.show_stations}|${parts.join("|")}`;
  }

  _render() {
    if (!this._hass || !this._config) return;
    const hass = this._hass;
    const model = buildModel(hass, this._config.entity);
    if (!model) {
      const sig = `missing|${this._config.entity}|${hass.language}`;
      if (this._sig !== sig) {
        this._sig = sig;
        this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card><div class="msg">${esc(t(hass, "missing"))}</div></ha-card>`;
      }
      return;
    }
    const sig = this._signature(model);
    if (sig === this._sig) return;
    this._sig = sig;
    this._model = model;

    const state = (id) => (id ? hass.states[id] : undefined);
    const progress = Number(state(model.progress)?.state) || 0;
    const current = state(model.current);
    const currentId = String(current?.attributes?.station_id ?? "");
    const running = state(model.running)?.state === "on";
    const released = state(model.treasure)?.state === "on";
    const circ = 2 * Math.PI * 52;
    const title = this._config.title ?? hass.states[model.progress]?.attributes?.friendly_name?.replace(/\s*(Fortschritt|Progress)$/i, "") ?? "";
    const c = model.controls;

    const btn = (id, cls, icon, label, confirmKey) =>
      id
        ? `<button class="${cls}" data-press="${esc(id)}" ${confirmKey ? `data-confirm="${confirmKey}"` : ""}><ha-icon icon="${icon}"></ha-icon>${esc(label)}</button>`
        : "";

    let select = "";
    const sel = state(model.select);
    if (sel) {
      const opts = sel.attributes.options || [];
      select = `<div><div class="label">${esc(t(hass, "station_select"))}</div>
        <select data-select="${esc(model.select)}">${opts
          .map((o) => `<option ${o === sel.state ? "selected" : ""}>${esc(o)}</option>`)
          .join("")}</select></div>`;
    }

    const taskBtn = (task) => {
      const on = hass.states[task.id]?.state === "on";
      return `<button class="task ${on ? "done" : ""}" data-task="${esc(task.id)}" data-on="${on}">
        <ha-icon icon="${on ? "mdi:check-circle" : task.icon || "mdi:checkbox-blank-circle-outline"}"></ha-icon>
        <span>${esc(task.name)}<small>${esc(on ? t(hass, "done") : t(hass, "open"))}${task.description ? " · " + esc(task.description) : ""}</small></span>
      </button>`;
    };

    const stationsHtml = this._config.show_stations
      ? model.stations
          .map(
            (st) => `<div class="st ${st.id === currentId ? "cur" : ""}">
          <h3><ha-icon icon="${st.icon || "mdi:map-marker"}"></ha-icon>${esc(st.id)} · ${esc(st.name)}</h3>
          <div class="btns">
            ${st.start ? `<button class="primary" data-press="${esc(st.start)}"><ha-icon icon="mdi:play"></ha-icon>${esc(t(hass, "start"))}</button>` : ""}
            ${st.clips.map((cl) => `<button data-press="${esc(cl.id)}"><ha-icon icon="${cl.icon || "mdi:movie-play"}"></ha-icon>${esc(cl.name)}</button>`).join("")}
          </div>
          ${st.tasks.map(taskBtn).join("")}
        </div>`
          )
          .join("") +
        (model.unassigned.length
          ? `<div class="st"><h3>${esc(t(hass, "other_tasks"))}</h3>${model.unassigned.map(taskBtn).join("")}</div>`
          : "")
      : "";

    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <ha-card>
        <div class="head">
          <div class="title">${esc(title)}</div>
          <div class="chips">
            <span class="chip ${running ? "on" : ""}">${esc(running ? t(hass, "running") : t(hass, "idle"))}</span>
            <span class="chip ${released ? "good" : ""}">${esc(released ? t(hass, "treasure_open") : t(hass, "treasure_locked"))}</span>
          </div>
        </div>
        <div class="top">
          <div class="ring">
            <svg viewBox="0 0 120 120"><circle class="bg" cx="60" cy="60" r="52" fill="none" stroke-width="10"/>
              <circle class="fg" cx="60" cy="60" r="52" fill="none" stroke-width="10" stroke-linecap="round"
                stroke-dasharray="${circ}" stroke-dashoffset="${circ * (1 - Math.min(100, progress) / 100)}"/></svg>
            <div class="num"><b>${progress}%</b><span>${esc(t(hass, "progress"))}</span></div>
          </div>
          <div class="side">
            <div><div class="label">${esc(t(hass, "current"))}</div><div class="current">${esc(current?.state ?? "–")}</div></div>
            <div class="btns">
              ${btn(c.prepare, "primary", "mdi:play-circle-outline", t(hass, "prepare"))}
              ${btn(c.stop, "danger", "mdi:stop-circle", t(hass, "stop"))}
            </div>
            ${select}
            <div class="btns">
              ${btn(c.release_treasure, "", "mdi:treasure-chest", t(hass, "release"), "confirm_release")}
              ${btn(c.reset, "danger", "mdi:restart", t(hass, "reset"), "confirm_reset")}
            </div>
          </div>
        </div>
        <div class="grid">${stationsHtml}</div>
      </ha-card>`;
  }

  _onClick(ev) {
    const el = ev.target.closest("button");
    if (!el || !this._hass) return;
    const confirmKey = el.dataset.confirm;
    if (confirmKey && !window.confirm(t(this._hass, confirmKey))) return;

    if (el.dataset.press) {
      this._hass.callService("button", "press", { entity_id: el.dataset.press });
    } else if (el.dataset.task) {
      const on = el.dataset.on === "true";
      if (on) {
        if (!window.confirm(t(this._hass, "confirm_undo"))) return;
        this._hass.callService("switch", "turn_off", { entity_id: el.dataset.task });
      } else {
        this._hass.callService("switch", "turn_on", { entity_id: el.dataset.task });
      }
    }
  }

  _onChange(ev) {
    const el = ev.target.closest("select[data-select]");
    if (!el || !this._hass) return;
    this._hass.callService("select", "select_option", { entity_id: el.dataset.select, option: el.value });
  }
}

class SchnitzeljagdCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._draw();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._form) this._form.hass = hass;
    else this._draw();
  }

  _draw() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (ev) => {
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: ev.detail.value }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    const hass = this._hass;
    this._form.hass = hass;
    this._form.data = this._config;
    this._form.computeLabel = (s) => t(hass, s.name);
    this._form.schema = [
      { name: "entity", selector: { entity: { integration: DOMAIN } } },
      { name: "title", selector: { text: {} } },
      { name: "show_stations", selector: { boolean: {} } },
    ];
  }
}

if (typeof customElements !== "undefined") {
  customElements.define("schnitzeljagd-card", SchnitzeljagdCard);
  customElements.define("schnitzeljagd-card-editor", SchnitzeljagdCardEditor);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "schnitzeljagd-card",
    name: "Schnitzeljagd",
    description: "Spielleitung für die Schnitzeljagd-Integration",
    preview: false,
  });
}

if (typeof module !== "undefined") module.exports = { buildModel };
})();
