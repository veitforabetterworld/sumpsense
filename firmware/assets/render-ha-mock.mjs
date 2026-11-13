// Aus sumpsense-16z/ha: node ../../assets/render-ha-mock.mjs  (Playwright hier installiert)
import {chromium} from "playwright";
import {fileURLToPath} from "url";
import path from "path";

const dir = path.dirname(fileURLToPath(import.meta.url));
const html = path.join(dir, "ha-dashboard-mock.html");
const png = path.join(dir, "ha-dashboard.png");

const browser = await chromium.launch();
const page = await browser.newPage({viewport: {width: 1120, height: 720}, deviceScaleFactor: 2});
await page.goto("file://" + html);
await page.screenshot({path: png});
await browser.close();
console.log(png);
