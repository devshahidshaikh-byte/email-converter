// All browser -> Python requests go through this single API base URL.
// For Netlify + Render, change API_BASE_URL in ../config.js.
// Keeping this in one place makes the frontend easy to deploy.
const API_BASE_URL = (window.APP_CONFIG?.API_BASE_URL || "").replace(/\/$/, "");

function apiUrl(path) {
  return `${API_BASE_URL}${path}`;
}

const API = {
  async request(path, options = {}) {
    const response = await fetch(apiUrl(path), {
      credentials: "include",
      ...options,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {})
      }
    });

    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json")
      ? await response.json()
      : await response.text();

    if (!response.ok) {
      const detail = data?.detail || data || "Request failed.";
      if (typeof detail === "object") {
        const message = Object.values(detail).filter(Boolean).join(" ");
        throw new Error(message || "Request failed.");
      }
      throw new Error(String(detail));
    }
    return data;
  },

  generate(payload) {
    return this.request("/api/generate", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },

  bulkGenerate(file) {
    const formData = new FormData();
    formData.append("file", file);

    return fetch(apiUrl("/api/private/bulk-generate"), {
      method: "POST",
      credentials: "include",
      headers: { "X-CSRF-Token": sessionStorage.getItem("csrf_token") || "" },
      body: formData
    }).then(async response => {
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Private bulk processing failed.");
      return data;
    });
  },

  export(payload, type) {
    return fetch(apiUrl(`/api/export/${encodeURIComponent(type)}`), {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": sessionStorage.getItem("csrf_token") || ""
      },
      body: JSON.stringify(payload)
    }).then(async response => {
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Export failed.");
      }
      return response.blob();
    })
  }
};
