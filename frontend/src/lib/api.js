const API_BASE = import.meta.env.VITE_FRAUDOPS_API_URL || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      "x-correlation-id": crypto.randomUUID(),
      ...(options.headers || {}),
    },
    ...options,
  });
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    throw new Error(typeof body === "string" ? body : body.detail || body.error || "API request failed");
  }
  return body;
}

export const api = {
  health: () => request("/health"),
  score: (payload) => request("/v1/transactions/score", { method: "POST", body: JSON.stringify(payload) }),
  transaction: (id) => request(`/v1/transactions/${id}`),
  alerts: () => request("/v1/alerts"),
  alert: (id) => request(`/v1/alerts/${id}`),
  createCase: (payload) => request("/v1/cases", { method: "POST", body: JSON.stringify(payload) }),
  getCase: (id) => request(`/v1/cases/${id}`),
  patchCase: (id, payload) => request(`/v1/cases/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  addAction: (id, payload) => request(`/v1/cases/${id}/actions`, { method: "POST", body: JSON.stringify(payload) }),
  resolveCase: (id, payload) => request(`/v1/cases/${id}/resolve`, { method: "POST", body: JSON.stringify(payload) }),
  model: () => request("/v1/models/current"),
  rules: () => request("/v1/rules"),
};
