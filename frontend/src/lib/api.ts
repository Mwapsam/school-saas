import { API, config } from "./config";
import { useAuthStore } from "./auth-store";

export class ApiError extends Error {
  status: number;
  data: unknown;
  constructor(message: string, status: number, data: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  /** Skip Authorization header (used for login/refresh). */
  anonymous?: boolean;
  /** Internal: prevents infinite refresh loops. */
  _retry?: boolean;
}

function buildUrl(path: string) {
  return path.startsWith("http") ? path : `${config.apiBaseUrl}${path}`;
}

/** Identifies this client to the backend's Manage Clients gate. Sent on every
 *  request, including anonymous ones (login/refresh) so a disabled client is
 *  turned away before authenticating. */
const clientHeaders: Record<string, string> = {
  "X-Client-App": config.clientApp,
  "X-Client-App-Version": config.clientAppVersion,
};

async function parseBody(res: Response) {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/** Refresh the access token using the stored refresh token. Returns the new
 *  access token, or null if refresh failed (caller should log out). A single
 *  transient failure (network error, non-auth status) is retried once after
 *  a short delay before giving up, so a brief blip doesn't force a logout. */
let refreshInFlight: Promise<string | null> | null = null;

async function attemptRefresh(refresh: string): Promise<{ access: string; refresh?: string } | "invalid" | "transient"> {
  try {
    const res = await fetch(buildUrl(API.refresh), {
      method: "POST",
      headers: { "Content-Type": "application/json", ...clientHeaders },
      body: JSON.stringify({ refresh }),
    });
    if (res.status === 401 || res.status === 403) return "invalid";
    if (!res.ok) return "transient";
    return (await res.json()) as { access: string; refresh?: string };
  } catch {
    return "transient";
  }
}

async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    const refresh = useAuthStore.getState().refresh;
    if (!refresh) return null;
    try {
      let result = await attemptRefresh(refresh);
      if (result === "transient") {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        result = await attemptRefresh(refresh);
      }
      if (result === "invalid" || result === "transient") return null;
      useAuthStore.getState().setTokens({
        access: result.access,
        refresh: result.refresh,
      });
      return result.access;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { body, anonymous, _retry, headers, ...rest } = options;
  const access = useAuthStore.getState().access;

  const res = await fetch(buildUrl(path), {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...clientHeaders,
      ...(anonymous || !access ? {} : { Authorization: `Bearer ${access}` }),
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  // Transparent refresh on 401, once.
  if (res.status === 401 && !anonymous && !_retry) {
    const newAccess = await refreshAccessToken();
    if (newAccess) {
      return apiFetch<T>(path, { ...options, _retry: true });
    }
    useAuthStore.getState().clear();
  }

  if (!res.ok) {
    const data = await parseBody(res);
    const message =
      (data && typeof data === "object" && "detail" in data
        ? String((data as Record<string, unknown>).detail)
        : null) ?? `Request failed (${res.status})`;
    throw new ApiError(message, res.status, data);
  }

  return (await parseBody(res)) as T;
}

/** POST multipart/form-data (file uploads) with the same auth/refresh handling
 *  as apiFetch. The browser sets the multipart boundary, so no Content-Type
 *  header is passed. */
export async function apiUpload<T>(
  path: string,
  form: FormData,
  options: { method?: string; _retry?: boolean } = {},
): Promise<T> {
  const access = useAuthStore.getState().access;
  const res = await fetch(buildUrl(path), {
    method: options.method ?? "POST",
    headers: {
      ...clientHeaders,
      ...(access ? { Authorization: `Bearer ${access}` } : {}),
    },
    body: form,
  });

  if (res.status === 401 && !options._retry) {
    const newAccess = await refreshAccessToken();
    if (newAccess) return apiUpload<T>(path, form, { ...options, _retry: true });
    useAuthStore.getState().clear();
  }

  if (!res.ok) {
    const data = await parseBody(res);
    const message =
      (data && typeof data === "object" && "detail" in data
        ? String((data as Record<string, unknown>).detail)
        : null) ?? `Upload failed (${res.status})`;
    throw new ApiError(message, res.status, data);
  }
  return (await parseBody(res)) as T;
}

/** Fetch a binary (e.g. PDF) response with the same auth/refresh handling as
 *  apiFetch, without JSON-parsing the body. Returns a Blob. */
export async function apiFetchBlob(
  path: string,
  options: RequestOptions = {},
): Promise<Blob> {
  const { anonymous, _retry, headers, body: _body, ...rest } = options;
  const access = useAuthStore.getState().access;

  const res = await fetch(buildUrl(path), {
    ...rest,
    headers: {
      ...clientHeaders,
      ...(anonymous || !access ? {} : { Authorization: `Bearer ${access}` }),
      ...headers,
    },
  });

  if (res.status === 401 && !anonymous && !_retry) {
    const newAccess = await refreshAccessToken();
    if (newAccess) {
      return apiFetchBlob(path, { ...options, _retry: true });
    }
    useAuthStore.getState().clear();
  }

  if (!res.ok) {
    throw new ApiError(`Request failed (${res.status})`, res.status, null);
  }

  return res.blob();
}
