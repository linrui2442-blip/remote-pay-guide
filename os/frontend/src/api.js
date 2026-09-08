const API_BASE = "http://localhost:8000";

async function parseResponse(response) {
  const payload = await response.json();
  if (!response.ok) {
    const message = payload?.detail || `Request failed with HTTP ${response.status}`;
    throw new Error(message);
  }
  return payload;
}

export async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`);
  return parseResponse(response);
}

export async function apiPost(path, data) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  return parseResponse(response);
}

export function buildDataCenterQueryParams(filters = {}) {
  const params = new URLSearchParams();
  const keys = [
    "account_id", "platform", "scope", "metrics", "sort_by", "sort_direction",
    "limit", "date_range", "start_date", "end_date", "interval",
  ];
  keys.forEach((key) => {
    const value = filters[key];
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  });
  if (filters.compare_previous_period) params.set("compare_previous_period", "true");
  return params;
}

export function getDataCenterQuery(filters = {}) {
  const params = buildDataCenterQueryParams(filters);
  return apiGet(`/data/query${params.toString() ? `?${params.toString()}` : ""}`);
}

export function buildAnalyticsBackfillRequest(filters = {}) {
  const request = {
    platform: filters.platform || undefined,
    date_range: filters.date_range || "28d",
  };
  if (request.date_range === "custom") {
    request.start_date = filters.start_date;
    request.end_date = filters.end_date;
  }
  return request;
}

export function planAnalyticsBackfill(accountId, filters = {}) {
  return apiPost(
    `/analytics/backfill/plan/${encodeURIComponent(accountId)}`,
    buildAnalyticsBackfillRequest(filters),
  );
}

export function createAnalyticsBackfillOperation(accountId, filters = {}) {
  return apiPost(
    `/analytics/backfill/operations/${encodeURIComponent(accountId)}`,
    buildAnalyticsBackfillRequest(filters),
  );
}

export function getAnalyticsBackfillOperation(operationId) {
  return apiGet(`/analytics/backfill/operations/${encodeURIComponent(operationId)}`);
}

export function listAnalyticsBackfillOperations(accountId, platform) {
  const params = new URLSearchParams();
  if (accountId != null && accountId !== "") params.set("account_id", String(accountId));
  if (platform) params.set("platform", platform);
  return apiGet(`/analytics/backfill/operations?${params.toString()}`);
}

export function cancelAnalyticsBackfillOperation(operationId) {
  return apiPost(
    `/analytics/backfill/operations/${encodeURIComponent(operationId)}/cancel`,
    {},
  );
}

export function isAnalyticsBackfillPollable(operation) {
  return ["queued", "running", "partial"].includes(operation?.status)
    || (operation?.status === "failed" && Boolean(operation?.next_retry_at));
}

export function getProductionTasks() { return apiGet('/production/tasks'); }
export function getProductionStatus() { return apiGet('/production/status'); }
export function getProductionProviders() { return apiGet('/production/providers'); }
export function createProductionTask(data) { return apiPost('/production/tasks', data); }
export function runProductionTask(id) { return apiPost(`/production/tasks/${id}/run`, {}); }
export function refreshProductionTask(id) { return apiPost(`/production/tasks/${id}/refresh`, {}); }

export function getPublishTasks() { return apiGet('/publish/tasks'); }
export function createPublishTask(data) { return apiPost('/publish/tasks', data); }
export function runPublishTask(id) {
  return apiPost(`/publish/tasks/${encodeURIComponent(id)}/run`, {});
}
export function collectPublishTaskAnalytics(id, data = {}) {
  return apiPost(`/analytics/collector/collect/publish-task/${encodeURIComponent(id)}`, data);
}
export function collectAccountAnalytics(accountId, platform, data = {}) {
  return apiPost(`/analytics/collector/collect/account/${encodeURIComponent(accountId)}`, {
    platform,
    active_limit: 10,
    ...data,
  });
}

export function getAccounts() { return apiGet('/accounts'); }
export function getSchedulerStatus() { return apiGet('/accounts/scheduler/status'); }
export function getSchedulerHistory(limit = 8) {
  return apiGet(`/accounts/scheduler/history?limit=${encodeURIComponent(limit)}`);
}
export function getSchedulerEvents(limit = 8) {
  return apiGet(`/accounts/scheduler/events?limit=${encodeURIComponent(limit)}`);
}
export function createAccount(data) { return apiPost('/accounts', data); }
export function getAccountSyncPlan(accountId) {
  return apiGet(`/accounts/${encodeURIComponent(accountId)}/sync-plan`);
}
export function syncAccount(accountId, maxResults = 10) {
  return apiPost(`/accounts/${encodeURIComponent(accountId)}/sync`, { max_results: maxResults });
}
export function syncAccountAll(accountId, data = {}) {
  return apiPost(`/accounts/${encodeURIComponent(accountId)}/sync-all`, {
    max_results: 10,
    sync_mode: 'incremental',
    ...data,
  });
}

export function getAccountConnectors() { return apiGet('/oauth/connectors'); }
export function beginPlatformOAuth(platform, accountId, scopeProfile = 'full') {
  return apiGet(
    `/oauth/connect/${encodeURIComponent(platform)}/${encodeURIComponent(accountId)}?scope_profile=${encodeURIComponent(scopeProfile)}`
  );
}
export function exchangePlatformOAuth(platform, data) {
  return apiPost(`/oauth/exchange/${encodeURIComponent(platform)}`, data);
}
export function getYouTubeOAuthStatus() { return apiGet('/oauth/youtube/status'); }
export function getAnalyticsCollectorStatus(platform, accountId) {
  const query = accountId == null ? '' : `?account_id=${encodeURIComponent(accountId)}`;
  return apiGet(`/analytics/collector/status/${encodeURIComponent(platform)}${query}`);
}
export function beginYouTubeOAuth(accountId, scopeProfile = 'full') {
  return beginPlatformOAuth('youtube', accountId, scopeProfile);
}
export function exchangeYouTubeOAuth(data) {
  return exchangePlatformOAuth('youtube', data);
}

export function getNetworkProxySettings() {
  return apiGet('/settings/network/proxy');
}

export function saveNetworkProxySettings(data) {
  return apiPost('/settings/network/proxy', data);
}

export function getAIGatewaySettings() {
  return apiGet('/settings/ai-gateway');
}

export function saveAIGatewaySettings(data) {
  return apiPost('/settings/ai-gateway', data);
}
