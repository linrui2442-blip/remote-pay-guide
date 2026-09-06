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

export function getProductionTasks() { return apiGet('/production/tasks'); }
export function getProductionStatus() { return apiGet('/production/status'); }
export function getProductionProviders() { return apiGet('/production/providers'); }
export function createProductionTask(data) { return apiPost('/production/tasks', data); }
export function runProductionTask(id) { return apiPost(`/production/tasks/${id}/run`, {}); }

export function getPublishTasks() { return apiGet('/publish/tasks'); }
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
export function getYouTubeOAuthStatus() { return apiGet('/oauth/youtube/status'); }
export function getAnalyticsCollectorStatus(platform, accountId) {
  const query = accountId == null ? '' : `?account_id=${encodeURIComponent(accountId)}`;
  return apiGet(`/analytics/collector/status/${encodeURIComponent(platform)}${query}`);
}
export function beginYouTubeOAuth(accountId, scopeProfile = 'full') {
  return beginPlatformOAuth('youtube', accountId, scopeProfile);
}

export function getNetworkProxySettings() {
  return apiGet('/settings/network/proxy');
}

export function saveNetworkProxySettings(data) {
  return apiPost('/settings/network/proxy', data);
}
