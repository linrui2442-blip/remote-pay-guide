const API_BASE = "http://localhost:8000";

export async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`);
  return response.json();
}
