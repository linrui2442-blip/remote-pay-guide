import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { buildDataCenterQueryParams } from "../src/api.js";

const page = await readFile(new URL("../src/pages/DataCenter.jsx", import.meta.url), "utf8");

for (const dateRange of ["7d", "28d", "90d", "lifetime"]) {
  const params = buildDataCenterQueryParams({
    scope: "active",
    date_range: dateRange,
    interval: "daily",
  });
  assert.equal(params.get("date_range"), dateRange);
  assert.equal(params.get("interval"), "daily");
}

const custom = buildDataCenterQueryParams({
  account_id: 7,
  platform: "youtube",
  scope: "active",
  date_range: "custom",
  start_date: "2026-08-01",
  end_date: "2026-08-28",
  compare_previous_period: true,
  interval: "daily",
});
assert.equal(custom.get("start_date"), "2026-08-01");
assert.equal(custom.get("end_date"), "2026-08-28");
assert.equal(custom.get("compare_previous_period"), "true");

const v1 = buildDataCenterQueryParams({scope: "historical", sort_by: "views"});
assert.equal(v1.get("scope"), "historical");
assert.equal(v1.has("date_range"), false);

assert.match(page, /useState\("28d"\)/, "28D must be the explicit UI default");
assert.match(page, /timeSeries\?\.available/, "trend availability must come from backend");
assert.match(page, /当前周期缺少真实每日 Analytics 快照，无法生成可信趋势。/);
assert.match(page, /scope === "active"/, "V2 must be limited to the supported active scope");
assert.match(page, /Historical \/ Archived \/ All 当前保留 Query V1 行为/);
assert.match(page, /query\.comparison/, "comparison must render backend response");
assert.doesNotMatch(page, /\/\s*28\b/, "frontend must not split a 28-day aggregate");

console.log("Data Center Query V2 frontend contract verification passed");
console.log("28D default; 7D/90D/lifetime/custom; comparison; truthful daily trend; V1 fallback");
