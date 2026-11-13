// Prüft den Konverter mit zigbee-herdsman-converters: Exposes und beide Richtungen.
// npm install zigbee-herdsman-converters && node test_converter.mjs
import conv from "./sumpsense-16z.mjs";
import * as zhc from "zigbee-herdsman-converters";
const def = zhc.prepareDefinition(conv);
const exposes = typeof def.exposes === "function" ? def.exposes(undefined, {}) : def.exposes;
console.log("Exposes:", exposes.map((e) => e.property || `${e.type}_${e.endpoint}`).join(", "));
const eps = {1: "level", 2: "valve", 3: "auto", 4: "lower", 5: "upper", 6: "fault"};
const writes = [];
const mkEp = (id) => ({ID: id, deviceIeeeAddress: "0x1", write: async (c, a) => writes.push([id, c, a]), command: async (c, cmd, p) => writes.push([id, c, cmd, p]), read: async (c, a) => writes.push([id, "read", c, a]), bind: async () => {}, configureReporting: async () => {}, getClusterAttributeValue: () => undefined, supportsInputCluster: () => true, saveClusterAttributeKeyValue: () => {}});
const endpoints = Object.keys(eps).map((k) => mkEp(+k));
const device = {ieeeAddr: "0x1", modelID: "SumpSense-16z", endpoints, getEndpoint: (id) => endpoints.find((e) => e.ID === id), customClusters: {}, save: () => {}};
const meta = {device, options: {}, state: {}, logger: console, deviceExposesChanged: () => {}};
let ok = 0, bad = 0;
const expect = (c, msg) => { if (c) ok++; else { bad++; console.log("FEHLER", msg); } };
expect(exposes.length === 6, "6 Exposes");
expect(def.ota === true || !!def.ota, "OTA aktiv");
async function fz(cluster, epId, data, type = "attributeReport") {
  const msg = {cluster, type, data, endpoint: device.getEndpoint(epId), device, meta: {}, linkquality: 100, groupID: 0};
  let r = {};
  for (const c of def.fromZigbee.filter((c) => c.cluster === cluster && [].concat(c.type).includes(type))) Object.assign(r, (await c.convert(def, msg, () => {}, {}, meta)) || {});
  return r;
}
let r = await fz("genAnalogInput", 1, {presentValue: 35});
expect(r.water_level_level === 35, "Wasserstand " + JSON.stringify(r));
r = await fz("genOnOff", 2, {onOff: 1});
expect(r.state_valve === "ON" && r.state_auto === undefined, "Ventil " + JSON.stringify(r));
r = await fz("genOnOff", 3, {onOff: 0});
expect(r.state_auto === "OFF", "Auto " + JSON.stringify(r));
r = await fz("genAnalogOutput", 4, {presentValue: 20});
expect(r.lower_threshold_lower === 20 && r.upper_threshold_upper === undefined, "Untere " + JSON.stringify(r));
r = await fz("genAnalogOutput", 5, {presentValue: 60});
expect(r.upper_threshold_upper === 60 && r.lower_threshold_lower === undefined, "Obere " + JSON.stringify(r));
r = await fz("genBinaryInput", 6, {presentValue: 1});
expect(r.fault_fault === true, "Störung " + JSON.stringify(r));
async function tz(key, value, epName) {
  const conv = def.toZigbee.find((t) => t.key.includes(key));
  const ep = device.getEndpoint(+Object.keys(eps).find((k) => eps[k] === epName));
  writes.length = 0;
  await conv.convertSet(ep, key, value, {...meta, endpoint_name: epName, message: {[key]: value}, mapped: def});
  return writes.slice();
}
let w = await tz("lower_threshold", 25, "lower");
expect(w[0][0] === 4 && w[0][1] === "genAnalogOutput" && w[0][2].presentValue === 25, "Schreiben untere " + JSON.stringify(w));
w = await tz("upper_threshold", 70, "upper");
expect(w[0][0] === 5 && w[0][2].presentValue === 70, "Schreiben obere " + JSON.stringify(w));
w = await tz("state", "ON", "valve");
expect(w[0][0] === 2 && w[0][1] === "genOnOff" && w[0][2] === "on", "Ventil an " + JSON.stringify(w));
w = await tz("state", "OFF", "auto");
expect(w[0][0] === 3 && w[0][2] === "off", "Auto aus " + JSON.stringify(w));
console.log(`${ok} Prüfungen, ${bad} Fehler`);
process.exit(bad ? 1 : 0);
