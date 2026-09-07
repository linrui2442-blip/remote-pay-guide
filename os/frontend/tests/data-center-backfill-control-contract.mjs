import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  buildAnalyticsBackfillRequest,
  cancelAnalyticsBackfillOperation,
  createAnalyticsBackfillOperation,
  getAnalyticsBackfillOperation,
  isAnalyticsBackfillPollable,
  planAnalyticsBackfill,
} from "../src/api.js";


const page = await readFile(
  new URL("../src/pages/DataCenter.jsx", import.meta.url),
  "utf8",
);

for (const dateRange of ["7d", "28d", "90d"]) {
  assert.deepEqual(buildAnalyticsBackfillRequest({
    platform: "youtube",
    date_range: dateRange,
  }), {platform: "youtube", date_range: dateRange});
}
assert.deepEqual(buildAnalyticsBackfillRequest({
  platform: "youtube",
  date_range: "custom",
  start_date: "2026-08-01",
  end_date: "2026-08-07",
}), {
  platform: "youtube",
  date_range: "custom",
  start_date: "2026-08-01",
  end_date: "2026-08-07",
});

const calls = [];
globalThis.fetch = async (url, options = {}) => {
  calls.push({url, options});
  if (url.includes("/plan/")) {
    return {
      ok: true,
      status: 200,
      json: async () => ({
        reporting_timezone: "America/Los_Angeles",
        period: {start_date: "2026-08-01", end_date: "2026-08-07"},
        eligible_videos: [{video_id: "v1"}],
        existing_dates: ["2026-08-01"],
        missing_dates: ["2026-08-02"],
        estimated_request_count: 1,
        request_cap: 500,
      }),
    };
  }
  if (url.endsWith("/cancel")) {
    return {ok: true, status: 200, json: async () => ({operation_id: 91, status: "cancelled"})};
  }
  if (options.method === "POST") {
    return {ok: true, status: 202, json: async () => ({operation_id: 91, status: "queued"})};
  }
  return {ok: true, status: 200, json: async () => ({operation_id: 91, status: "success"})};
};

const plan = await planAnalyticsBackfill(7, {platform: "youtube", date_range: "7d"});
assert.equal(plan.reporting_timezone, "America/Los_Angeles");
assert.equal(calls.length, 1, "planning must not create an operation");
assert.match(calls[0].url, /\/analytics\/backfill\/plan\/7$/);

const created = await createAnalyticsBackfillOperation(7, {
  platform: "youtube",
  date_range: "7d",
});
assert.equal(created.operation_id, 91);
assert.equal(created.status, "queued");
assert.match(calls[1].url, /\/analytics\/backfill\/operations\/7$/);

assert.equal(isAnalyticsBackfillPollable({status: "queued"}), true);
assert.equal(isAnalyticsBackfillPollable({status: "running"}), true);
assert.equal(isAnalyticsBackfillPollable({status: "partial"}), true);
assert.equal(isAnalyticsBackfillPollable({status: "failed", next_retry_at: "2026-08-08T00:00:00Z"}), true);
assert.equal(isAnalyticsBackfillPollable({status: "failed", next_retry_at: null}), false);
assert.equal(isAnalyticsBackfillPollable({status: "success"}), false);
assert.equal(isAnalyticsBackfillPollable({status: "cancelled"}), false);

const finished = await getAnalyticsBackfillOperation(91);
assert.equal(finished.status, "success");
const cancelled = await cancelAnalyticsBackfillOperation(91);
assert.equal(cancelled.status, "cancelled");

assert.match(page, /检查缺失数据/);
assert.match(page, /开始历史数据回填/);
assert.match(page, /reporting_timezone/);
assert.match(page, /eligible_videos/);
assert.match(page, /existing_dates/);
assert.match(page, /missing_dates/);
assert.match(page, /estimated_request_count/);
assert.match(page, /progress_percentage/);
assert.match(page, /系统将在 .* 后自动重试/);
assert.match(page, /取消剩余回填/);
assert.match(page, /取消不会删除已经成功写入的历史 Analytics/);
assert.match(page, /该账号已有正在进行的历史数据回填任务/);
assert.match(page, /operation\?\.status !== "success"/);
assert.match(page, /onSuccess\(\)/, "successful operation must refresh Query V2");
assert.match(page, /window\.clearInterval\(timer\)/, "polling must clean up");
assert.doesNotMatch(page, /\/analytics\/backfill\/run\//);
assert.match(
  page,
  /const startBackfill = async \(\) =>[\s\S]*createAnalyticsBackfillOperation/,
  "operation creation must remain inside the explicit start handler",
);
assert.match(
  page,
  /useEffect\(\(\) => \{[\s\S]*listAnalyticsBackfillOperations/,
  "initialization may read existing operations but must not create one",
);

console.log("Data Center backfill control plane contract verification passed");
console.log("plan/run separation; range mapping; polling/cancel/retry; Query V2 refresh");
