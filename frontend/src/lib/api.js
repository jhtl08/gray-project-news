export const API_BASE = "http://localhost:8000";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function readError(res) {
  const fallback = `Request failed (${res.status})`;
  try {
    const body = await res.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object") {
      if (detail.traceback) console.error("Backend traceback:", detail.traceback);
      return detail.error || JSON.stringify(detail);
    }
    return fallback;
  } catch {
    return res.statusText || fallback;
  }
}

/**
 * One place for the base URL, FastAPI's error shapes and the network message.
 * An aborted request is rethrown untouched, so callers can ignore it.
 */
export async function apiFetch(path, options = {}) {
  const { signal, ...init } = options;
  let res;

  try {
    // Data views must never render a cached body for a refresh.
    res = await fetch(`${API_BASE}${path}`, { cache: "no-store", ...init, signal });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError(`Can't reach the API at ${API_BASE}. Check that the server is running.`);
  }

  if (!res.ok) throw new ApiError(await readError(res), res.status);
  if (res.status === 204) return null;

  try {
    return await res.json();
  } catch {
    return null;
  }
}

export function apiPost(path, body, options = {}) {
  return apiFetch(path, {
    method: "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    ...options,
  });
}

export function apiDelete(path, options = {}) {
  return apiFetch(path, { method: "DELETE", ...options });
}
