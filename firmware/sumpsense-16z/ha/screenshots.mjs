// Richtet eine frische Home-Assistant-Testinstanz ein (MQTT, Dashboard) und
// erstellt Screenshots vom simulierten SumpSense-16z (sim.mjs muss laufen).
// Aufruf: node screenshots.mjs <Ausgabeordner> [http://localhost:8123]
import {chromium} from "playwright";

const out = process.argv[2] || ".";
const HA = process.argv[3] || "http://localhost:8123";
const CID = HA + "/";

async function j(r) {
    const t = await r.text();
    try { return JSON.parse(t); } catch { throw new Error(`${r.status} ${t.slice(0, 200)}`); }
}

// Anmeldung über trusted_networks (Testinstanz ohne Passwort)
async function token() {
    let f = await j(await fetch(`${HA}/auth/login_flow`, {method: "POST", headers: {"content-type": "application/json"},
        body: JSON.stringify({client_id: CID, handler: ["trusted_networks", null], redirect_uri: CID + "?auth_callback=1"})}));
    if (f.type === "form") {
        const user = f.data_schema[0].options ? Object.keys(f.data_schema[0].options)[0] : undefined;
        f = await j(await fetch(`${HA}/auth/login_flow/${f.flow_id}`, {method: "POST", headers: {"content-type": "application/json"},
            body: JSON.stringify({client_id: CID, user})}));
    }
    const tok = await j(await fetch(`${HA}/auth/token`, {method: "POST", headers: {"content-type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({grant_type: "authorization_code", code: f.result, client_id: CID})}));
    return tok.access_token;
}

function ws(tok) {
    return new Promise((res) => {
        const s = new WebSocket(HA.replace("http", "ws") + "/api/websocket");
        let id = 1;
        const pending = new Map();
        s.onmessage = (e) => {
            const m = JSON.parse(e.data);
            if (m.type === "auth_required") s.send(JSON.stringify({type: "auth", access_token: tok}));
            else if (m.type === "auth_ok") res({call: (msg) => new Promise((r) => { const i = id++; pending.set(i, r); s.send(JSON.stringify({...msg, id: i})); }), close: () => s.close()});
            else if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
        };
    });
}

const tok = await token();
const H = {authorization: `Bearer ${tok}`, "content-type": "application/json"};
const api = async (p, body) => j(await fetch(HA + p, body === undefined ? {headers: H} : {method: "POST", headers: H, body: JSON.stringify(body)}));

// MQTT-Integration anlegen, falls noch nicht vorhanden
const entries = await api("/api/config/config_entries/entry");
if (!entries.some((e) => e.domain === "mqtt")) {
    let f = await api("/api/config/config_entries/flow", {handler: "mqtt", show_advanced_options: false});
    if (f.type === "menu") f = await api(`/api/config/config_entries/flow/${f.flow_id}`, {next_step_id: "broker"});
    f = await api(`/api/config/config_entries/flow/${f.flow_id}`, {broker: "mosquitto", port: 1883});
    console.log("MQTT:", f.type, f.title || f.errors || "");
    await new Promise((r) => setTimeout(r, 8000));
}

const c = await ws(tok);
await c.call({type: "frontend/set_user_data", key: "language", value: {language: "de", number_format: "language"}});
const ents = (await c.call({type: "config/entity_registry/list"})).result.filter((e) => e.platform === "mqtt");
const byObj = (s) => ents.find((e) => e.unique_id.includes(s))?.entity_id;
const E = {
    level: byObj("_water_level_level_"), valve: byObj("_switch_valve_"), auto: byObj("_switch_auto_"),
    lower: byObj("_lower_threshold_lower_"), upper: byObj("_upper_threshold_upper_"), fault: byObj("_fault_fault_"),
};
console.log(E);
const deviceId = ents.find((e) => e.entity_id === E.level).device_id;

// Dashboard "Bewässerung"
await c.call({type: "lovelace/dashboards/create", url_path: "bewaesserung", title: "Bewässerung", icon: "mdi:sprinkler-variant", mode: "storage", require_admin: false, show_in_sidebar: true});
await c.call({type: "lovelace/config/save", url_path: "bewaesserung", config: {
    title: "Bewässerung",
    views: [{title: "SumpSense", path: "sumpsense", type: "sections", max_columns: 2, sections: [
        {type: "grid", cards: [
            {type: "heading", heading: "Wasserstand", icon: "mdi:waves-arrow-up"},
            {type: "gauge", entity: E.level, name: "Wasserstand", min: 0, max: 80, unit: "mm", needle: true,
                segments: [{from: 0, color: "#db4437"}, {from: 20, color: "#ffa600"}, {from: 30, color: "#43a047"}, {from: 70, color: "#039be5"}],
                grid_options: {columns: 6, rows: 4}},
            {type: "tile", entity: E.valve, name: "Ventil", features: [{type: "toggle"}], grid_options: {columns: 6, rows: 2}},
            {type: "tile", entity: E.auto, name: "Gieß-Automatik", features: [{type: "toggle"}], grid_options: {columns: 6, rows: 2}},
            {type: "history-graph", title: "Verlauf", hours_to_show: 1, entities: [{entity: E.level, name: "Wasserstand"}, {entity: E.valve, name: "Ventil"}]},
        ]},
        {type: "grid", cards: [
            {type: "heading", heading: "Automatik", icon: "mdi:tune-variant"},
            {type: "tile", entity: E.lower, name: "Untere Schwelle (Ventil auf)", features: [{type: "numeric-input", style: "buttons"}]},
            {type: "tile", entity: E.upper, name: "Obere Schwelle (Ventil zu)", features: [{type: "numeric-input", style: "buttons"}]},
            {type: "tile", entity: E.fault, name: "Störung"},
            {type: "markdown", content: "Die Automatik öffnet das Ventil, wenn der Wasserstand auf die **untere Schwelle** fällt, und schließt es bei der **oberen Schwelle**. Nach 10 min ohne Erfolg schließt das Ventil und meldet eine Störung."},
        ]},
    ]}],
}});
c.close();

const browser = await chromium.launch();
for (const scheme of ["light", "dark"]) {
    const ctx = await browser.newContext({viewport: {width: 1280, height: 860}, deviceScaleFactor: 1, colorScheme: scheme, locale: "de-DE"});
    const page = await ctx.newPage();
    await page.addInitScript(() => localStorage.setItem("selectedLanguage", '"de"'));
    await page.goto(HA + "/bewaesserung/sumpsense");
    await page.waitForTimeout(9000);
    await page.screenshot({path: `${out}/ha-dashboard-${scheme}.png`});
    if (scheme === "light") {
        await page.goto(`${HA}/config/devices/device/${deviceId}`);
        await page.waitForTimeout(7000);
        await page.screenshot({path: `${out}/ha-geraet.png`, fullPage: true});
    }
    await ctx.close();
}
await browser.close();
console.log("Screenshots in", out);
