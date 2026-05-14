const JSON_HEADERS = { "Content-Type": "application/json" };

async function parseJson(res) {
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Request failed (${res.status}): ${body || res.statusText}`);
  }
  return res.json();
}

async function get(path) {
  const res = await fetch(path, { headers: JSON_HEADERS });
  return parseJson(res);
}

async function post(path, payload) {
  const res = await fetch(path, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(payload || {}),
  });
  return parseJson(res);
}

async function put(path, payload) {
  const res = await fetch(path, {
    method: "PUT",
    headers: JSON_HEADERS,
    body: JSON.stringify(payload || {}),
  });
  return parseJson(res);
}

export const api = {
  health: () => get("/api/health"),
  reseed: (seed) => post("/api/reseed", { seed }),
  customers: () => get("/api/customers"),
  shipments: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return get(`/api/shipments${q ? `?${q}` : ""}`);
  },
  shipment: (id) => get(`/api/shipments/${id}`),
  messages: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return get(`/api/messages${q ? `?${q}` : ""}`);
  },
  sendMessage: (payload) => post("/api/messages", payload),
  tickets: () => get("/api/tickets"),
  setTicketStatus: (id, status) => post(`/api/tickets/${id}/status`, { status }),
  replyTicket: (id, text) => post(`/api/tickets/${id}/reply`, { text }),
  agentReplyTicket: (id) => post(`/api/tickets/${id}/agent-reply`),
  broadcasts: () => get("/api/broadcasts"),
  agentActions: () => get("/api/agent-actions"),
  agentConfig: () => get("/api/agent-config"),
  updateAgentConfig: (patch) => put("/api/agent-config", patch),
  departments: () => get("/api/departments"),
  assignTicket: (id, patch) => post(`/api/tickets/${id}/assign`, patch),
  kpis: () => get("/api/kpis"),
  nudges: () => get("/api/nudges"),
  sendNudge: (id) => post(`/api/nudges/${id}/send`),
  cancelNudge: (id) => post(`/api/nudges/${id}/cancel`),
  approvals: () => get("/api/approvals"),
  decideApproval: (id, decision, text) => post(`/api/approvals/${id}/decide`, { decision, text }),
  agentRuns: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return get(`/api/agent-runs${q ? `?${q}` : ""}`);
  },
};
