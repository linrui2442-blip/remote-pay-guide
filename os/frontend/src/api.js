const API_BASE = "http://localhost:8000";

export async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`);
  return response.json();
}

export async function apiPost(path, data) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  return response.json();
}

export function getProductionTasks() { return apiGet('/production/tasks'); }
export function getProductionStatus() { return apiGet('/production/status'); }
export function getProductionProviders() { return apiGet('/production/providers'); }
export function createProductionTask(data) { return apiPost('/production/tasks', data); }
export function runProductionTask(id) { return apiPost(`/production/tasks/${id}/run`, {}); }
