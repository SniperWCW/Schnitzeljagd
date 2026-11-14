// Test der Entity-Erkennung der Karte: node tests/card.test.js
const assert = require("assert");
const path = require("path");

// Minimale Browser-Stubs, damit die Datei außerhalb des Browsers lädt
const defined = {};
global.window = global;
global.HTMLElement = class {
  attachShadow() {
    this.shadowRoot = { innerHTML: "", addEventListener() {} };
    return this.shadowRoot;
  }
};
global.customElements = { define: (name, cls) => (defined[name] = cls) };
const { buildModel } = require(path.join(__dirname, "..", "custom_components", "schnitzeljagd", "frontend", "schnitzeljagd-card.js"));

const dev = "dev1";
const ent = (platform = "schnitzeljagd", extra = {}) => ({ platform, device_id: dev, ...extra });
const entities = {
  "sensor.j_fortschritt": ent("schnitzeljagd", { translation_key: "progress" }),
  "sensor.j_aktuelle_station": ent("schnitzeljagd", { translation_key: "current_station" }),
  "binary_sensor.j_spiel_lauft": ent("schnitzeljagd", { translation_key: "running" }),
  "binary_sensor.j_schatz": ent("schnitzeljagd", { translation_key: "treasure" }),
  "select.j_station": ent("schnitzeljagd", { translation_key: "station" }),
  "button.j_prepare": ent("schnitzeljagd", { translation_key: "prepare" }),
  "button.j_reset": ent("schnitzeljagd", { translation_key: "reset" }),
  "button.j_start_2": ent(),
  "button.j_start_1": ent(),
  "button.j_clip": ent(),
  "switch.j_t2": ent(),
  "switch.j_t1": ent(),
  "switch.j_t0": ent(),
  "switch.fremd": ent("other"),
};
const states = {
  "sensor.j_fortschritt": { state: "14", attributes: {} },
  "sensor.j_aktuelle_station": { state: "1 · Esszimmer", attributes: { station_id: "1" } },
  "binary_sensor.j_spiel_lauft": { state: "off", attributes: {} },
  "binary_sensor.j_schatz": { state: "off", attributes: {} },
  "select.j_station": { state: "1 · Esszimmer", attributes: { options: ["1 · Esszimmer", "2 · Gästezimmer"] } },
  "button.j_prepare": { state: "unknown", attributes: {} },
  "button.j_reset": { state: "unknown", attributes: {} },
  "button.j_start_2": { state: "unknown", attributes: { kind: "station", station_id: "2", station_name: "Gästezimmer", order: 1 } },
  "button.j_start_1": { state: "unknown", attributes: { kind: "station", station_id: "1", station_name: "Esszimmer", order: 0 } },
  "button.j_clip": { state: "unknown", attributes: { kind: "clip", station_id: "2", clip_name: "Finale" } },
  "switch.j_t2": { state: "off", attributes: { task_name: "B", station: "2", order: 2 } },
  "switch.j_t1": { state: "on", attributes: { task_name: "A2", station: "1", order: 1 } },
  "switch.j_t0": { state: "off", attributes: { task_name: "A1", station: "1", order: 0 } },
  "switch.fremd": { state: "on", attributes: {} },
};
const hass = { entities, states };

const m = buildModel(hass, "sensor.j_fortschritt");
assert.strictEqual(m.progress, "sensor.j_fortschritt");
assert.strictEqual(m.current, "sensor.j_aktuelle_station");
assert.strictEqual(m.select, "select.j_station");
assert.strictEqual(m.controls.prepare, "button.j_prepare");
assert.deepStrictEqual(m.stations.map((s) => s.id), ["1", "2"]);
assert.strictEqual(m.stations[0].start, "button.j_start_1");
assert.deepStrictEqual(m.stations[0].tasks.map((x) => x.name), ["A1", "A2"]);
assert.strictEqual(m.stations[1].clips.length, 1);
assert.strictEqual(m.tasks.length, 3, "Fremd-Plattform wird ignoriert");
assert.strictEqual(buildModel(hass, "switch.fremd"), null);
assert.strictEqual(buildModel(hass, "sensor.gibtsnicht"), null);
console.log("card tests ok");

// Render-Test
const card = new defined["schnitzeljagd-card"]();
card.setConfig({ entity: "sensor.j_fortschritt", title: "Spielleitung" });
card.hass = { ...hass, language: "de" };
const html = card.shadowRoot.innerHTML;
assert.ok(html.includes("14%"), "Fortschritt");
assert.ok(html.includes("Spielleitung"), "Titel");
assert.ok(html.includes("1 · Esszimmer"), "Station");
assert.ok(html.includes('data-press="button.j_start_2"'), "Start-Button");
assert.ok(html.includes('data-task="switch.j_t1" data-on="true"'), "erledigte Aufgabe");
assert.ok(html.includes("Schatz gesperrt"), "Schatzstatus");
card.setConfig({ entity: "sensor.gibtsnicht" });
card.hass = { ...hass, language: "en" };
assert.ok(card.shadowRoot.innerHTML.includes("not found"), "Fehlermeldung");
console.log("card render ok");
