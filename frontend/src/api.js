let csrfToken = "";

export function setCsrfToken(token) {
  csrfToken = token || "";
}

export async function api(path, options = {}) {
  const method = options.method || "GET";
  const headers = { ...(options.headers || {}) };
  if (csrfToken && !["GET", "HEAD"].includes(method)) headers["X-CSRF-Token"] = csrfToken;
  let body = options.body;
  if (body !== undefined && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(body);
  }
  const response = await fetch(`/api${path}`, { ...options, method, headers, body, credentials: "same-origin" });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) {
    const error = new Error(payload.error || `请求失败（${response.status}）`);
    error.status = response.status;
    error.code = payload.code;
    throw error;
  }
  if (payload.data?.csrfToken) setCsrfToken(payload.data.csrfToken);
  return payload.data;
}

export async function downloadCsv(path, filename) {
  const response = await fetch(`/api${path}`, { credentials: "same-origin" });
  if (!response.ok) throw new Error("导出失败");
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
