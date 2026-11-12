const TOKEN_KEY = "support_agent_ai_token";

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* storage unavailable: the person will need to sign in again next visit */
  }
}

export function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

export class ApiError extends Error {
  constructor(message, status, fieldErrors) {
    super(message);
    this.status = status;
    this.fieldErrors = fieldErrors || {};
  }
}

async function request(path, { method = "GET", body, auth = false } = {}) {
  const isForm = body instanceof FormData;
  const headers = {};
  if (!isForm) headers["Content-Type"] = "application/json";
  if (auth && getToken()) headers.Authorization = "Bearer " + getToken();

  let response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers,
      body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
    });
  } catch {
    throw new ApiError("Can’t reach the server. Check your connection and try again.", 0);
  }

  let data = {};
  try {
    data = await response.json();
  } catch {
    /* non-JSON response */
  }

  if (!response.ok) {
    if (response.status === 413) {
      throw new ApiError("That file is too large. The maximum size is 5 MB.", 413);
    }
    throw new ApiError(data.message || "Something went wrong. Please try again.", response.status, data.errors);
  }
  return data;
}

export const api = {
  register: (form) => request("/register/", { method: "POST", body: form }),
  login: (email, password) => request("/login/", { method: "POST", body: { email, password } }),
  me: () => request("/me/", { auth: true }),
  getDocument: () => request("/document/", { auth: true }),
  uploadDocument: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/document/", { method: "POST", body: form, auth: true });
  },
  deleteDocument: () => request("/document/", { method: "DELETE", auth: true }),
  reindexDocument: () => request("/document/reindex/", { method: "POST", auth: true }),
  searchDocument: (query) => request("/document/search/", { method: "POST", body: { query }, auth: true }),
  getBotSettings: () => request("/bot-settings/", { auth: true }),
  saveBotSettings: (settings) => request("/bot-settings/", { method: "POST", body: settings, auth: true }),
  getPublication: () => request("/publication/", { auth: true }),
  getAnalytics: () => request("/analytics/", { auth: true }),
  getWidgetMode: () => request("/bot-settings/widget/", { auth: true }),
  setWidgetMode: (widget_mode) => request("/bot-settings/widget/", { method: "POST", body: { widget_mode }, auth: true }),
  publishBot: () => request("/publication/publish/", { method: "POST", body: {}, auth: true }),
  unpublishBot: () => request("/publication/unpublish/", { method: "POST", body: {}, auth: true }),
  restoreVersion: (id) =>
    request(`/publication/versions/${id}/restore/`, { method: "POST", body: {}, auth: true }),
  getApiKey: () => request("/publication/api-key/", { auth: true }),
  rotateApiKey: () => request("/publication/api-key/", { method: "POST", body: {}, auth: true }),
  revokeApiKeys: () => request("/publication/api-key/", { method: "DELETE", auth: true }),
  getAllowedWebsites: () => request("/publication/websites/", { auth: true }),
  addAllowedWebsite: (origin) =>
    request("/publication/websites/", { method: "POST", body: { origin }, auth: true }),
  removeAllowedWebsite: (origin) =>
    request("/publication/websites/", { method: "DELETE", body: { origin }, auth: true }),
};
