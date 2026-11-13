// Simuliert ein SumpSense-16z hinter Zigbee2MQTT für Home-Assistant-Screenshots.
// Discovery und Zustand im Format von Zigbee2MQTT (Konverter ../z2m/sumpsense-16z.mjs),
// Regelverhalten wie ss_logic.c (Hysterese zwischen unterer und oberer Schwelle).
// Aufruf: node sim.mjs [mqtt://localhost:1883] [Sekunden]
import mqtt from "mqtt";

const url = process.argv[2] || "mqtt://localhost:1883";
const runFor = Number(process.argv[3] || 600);
const ieee = "0x48be2dfffe1a6c01";
const name = "SumpSense-16z";
const base = `zigbee2mqtt/${name}`;
const device = {
    identifiers: [`zigbee2mqtt_${ieee}`],
    name,
    model: "Kapazitiver Füllstandssensor (16 Stufen, 5 mm) mit Gieß-Automatik",
    model_id: "SumpSense-16z",
    manufacturer: "SumpSense",
    sw_version: "1.0.0",
    via_device: "zigbee2mqtt_bridge_0x00124b0029a1b2c3",
};
const avail = [{topic: "zigbee2mqtt/bridge/state", value_template: "{{ value_json.state }}"}];
const common = {device, availability: avail, state_topic: base, json_attributes_topic: base, origin: {name: "Zigbee2MQTT", sw: "2.6.3", url: "https://www.zigbee2mqtt.io"}};

const entities = [
    ["sensor", "water_level_level", {name: "Wasserstand", unit_of_measurement: "mm", state_class: "measurement", icon: "mdi:waves-arrow-up",
        value_template: "{{ value_json.water_level_level }}"}],
    ["switch", "switch_valve", {name: "Ventil", icon: "mdi:valve", value_template: "{{ value_json.state_valve }}",
        state_on: "ON", state_off: "OFF", command_topic: `${base}/set`, payload_on: '{"state_valve": "ON"}', payload_off: '{"state_valve": "OFF"}'}],
    ["switch", "switch_auto", {name: "Gieß-Automatik", icon: "mdi:sprinkler-variant", value_template: "{{ value_json.state_auto }}",
        state_on: "ON", state_off: "OFF", command_topic: `${base}/set`, payload_on: '{"state_auto": "ON"}', payload_off: '{"state_auto": "OFF"}'}],
    ["number", "lower_threshold_lower", {name: "Untere Schwelle", entity_category: "config", unit_of_measurement: "mm", min: 5, max: 80, step: 5,
        icon: "mdi:arrow-collapse-down", value_template: "{{ value_json.lower_threshold_lower }}", command_topic: `${base}/set/lower_threshold_lower`}],
    ["number", "upper_threshold_upper", {name: "Obere Schwelle", entity_category: "config", unit_of_measurement: "mm", min: 5, max: 80, step: 5,
        icon: "mdi:arrow-collapse-up", value_template: "{{ value_json.upper_threshold_upper }}", command_topic: `${base}/set/upper_threshold_upper`}],
    ["binary_sensor", "fault_fault", {name: "Störung", device_class: "problem", entity_category: "diagnostic",
        value_template: "{{ value_json.fault_fault }}", payload_on: true, payload_off: false}],
    ["sensor", "linkquality", {name: "Linkqualität", entity_category: "diagnostic", unit_of_measurement: "lqi", state_class: "measurement",
        icon: "mdi:signal", value_template: "{{ value_json.linkquality }}"}],
    ["update", "update", {name: null, device_class: "firmware", entity_category: "config", entity_picture: null,
        latest_version_template: "{{ value_json.update.latest_version }}", value_template: "{{ value_json.update.installed_version }}",
        command_topic: "zigbee2mqtt/bridge/request/device/ota_update/update", payload_install: `{"id": "${ieee}"}`}],
];

const st = {water_level_level: 35, state_valve: "OFF", state_auto: "ON", lower_threshold_lower: 20, upper_threshold_upper: 60,
    fault_fault: false, linkquality: 168, update: {state: "idle", installed_version: 1, latest_version: 1}};
const fmtUpdate = () => ({...st, update: {state: "idle", installed_version: "1.0.0", latest_version: "1.0.0"}});

const c = mqtt.connect(url);
const pub = () => c.publish(base, JSON.stringify(fmtUpdate()), {retain: true});
c.on("connect", () => {
    c.publish("zigbee2mqtt/bridge/state", JSON.stringify({state: "online"}), {retain: true});
    for (const [comp, id, cfg] of entities) {
        const payload = {...common, ...cfg, object_id: `sumpsense-16z_${id}`, unique_id: `${ieee}_${id}_zigbee2mqtt`};
        if (comp === "update") delete payload.json_attributes_topic;
        c.publish(`homeassistant/${comp}/${ieee}/${id}/config`, JSON.stringify(payload), {retain: true});
    }
    c.subscribe([`${base}/set`, `${base}/set/+`]);
    pub();
    console.log("Discovery gesendet");
});
c.on("message", (topic, msg) => {
    const s = msg.toString();
    if (topic.endsWith("/set")) Object.assign(st, JSON.parse(s));
    else st[topic.split("/").pop()] = Math.round(Number(s) / 5) * 5;
    if (st.lower_threshold_lower + 5 > st.upper_threshold_upper) st.lower_threshold_lower = st.upper_threshold_upper - 5;
    pub();
});
// Füllstand: fällt langsam (Verdunstung/Pflanze), steigt bei offenem Ventil
let t = 0;
setInterval(() => {
    t++;
    const lv = st.water_level_level;
    if (st.state_valve === "ON") st.water_level_level = Math.min(80, lv + 5);
    else if (t % 3 === 0) st.water_level_level = Math.max(0, lv - 5);
    if (st.state_auto === "ON") {
        if (st.state_valve === "OFF" && st.water_level_level <= st.lower_threshold_lower) st.state_valve = "ON";
        else if (st.state_valve === "ON" && st.water_level_level >= st.upper_threshold_upper) st.state_valve = "OFF";
    }
    st.linkquality = 160 + Math.round(Math.random() * 20);
    pub();
}, 4000);
setTimeout(() => { console.log("Ende"); c.end(); process.exit(0); }, runFor * 1000);
