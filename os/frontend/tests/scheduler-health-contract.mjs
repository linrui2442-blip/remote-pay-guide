import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const api = readFileSync(resolve(here, "../src/api.js"), "utf8");
const app = readFileSync(resolve(here, "../src/App.jsx"), "utf8");

assert.match(api, /getSchedulerStatus\(\).*\/accounts\/scheduler\/status/);
assert.match(api, /getSchedulerHistory[\s\S]*?\/accounts\/scheduler\/history/);
assert.match(api, /getSchedulerEvents[\s\S]*?\/accounts\/scheduler\/events/);
assert.match(app, /Scheduler Health/);
assert.match(app, /Last Check/);
assert.match(app, /Current Run Age/);
assert.match(app, /Last Completed Sync/);
assert.match(app, /Last Duration/);
assert.match(app, /Renewing/);
assert.match(app, /At Risk/);
assert.match(app, /Accounts Due/);
assert.match(app, /Accounts Retrying/);
assert.match(app, /Active Lease/);
assert.match(app, /Recent Runs/);
assert.match(app, /Reporting Day/);
assert.match(app, /Recent Health Events/);
assert.match(app, /No health transitions yet/);
assert.doesNotMatch(app, /run_once/);

console.log("Scheduler health frontend contract passed");
