/**
 * The HTTP concern shared by every API client in the app.
 *
 * Split out of data.ts once a second resource needed it, so the gene client,
 * the auth client and the users client agree on how a request is made, how
 * CSRF is handled and how a failure is reported.
 */

/** Same-origin by default; set VITE_API_URL when the API is on another host. */
export const API = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  // Written in the body rather than as parameter properties: the project
  // compiles with erasableSyntaxOnly, which disallows that shorthand.
  status: number;
  suggestions: string[];
  /** Per-field messages from a DRF serializer, for showing beside inputs. */
  fields: Record<string, string[]>;

  constructor(
    message: string,
    status: number,
    suggestions: string[] = [],
    fields: Record<string, string[]> = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.suggestions = suggestions;
    this.fields = fields;
  }
}

/** Django writes the token here; it is deliberately readable by script. */
function csrfFromCookie(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

/**
 * Ensure a CSRF cookie exists.
 *
 * Django only sets it on a view that asks for it, so the client fetches one
 * before the first unsafe request rather than after a confusing 403.
 */
export async function ensureCsrfToken(): Promise<string> {
  const existing = csrfFromCookie();
  if (existing) return existing;

  const res = await fetch(`${API}/api/auth/csrf/`, { credentials: "include" });
  if (!res.ok) throw new ApiError("Could not reach the server.", res.status);
  const body: { csrfToken: string } = await res.json();
  return body.csrfToken;
}

/**
 * Turn a failed response into an ApiError.
 *
 * DRF reports errors three ways depending on where they came from — a bare
 * `detail`, `non_field_errors`, or a map of field name to messages — and a
 * form needs all three: the first two as a banner, the last beside the input.
 */
async function toError(res: Response): Promise<ApiError> {
  let detail = `Request failed (${res.status})`;
  let suggestions: string[] = [];
  const fields: Record<string, string[]> = {};

  try {
    const body = await res.json();
    if (typeof body.detail === "string") detail = body.detail;
    if (Array.isArray(body.suggestions)) suggestions = body.suggestions;

    for (const [key, value] of Object.entries(body)) {
      if (key === "detail" || key === "suggestions") continue;
      const messages = Array.isArray(value) ? value.map(String) : [String(value)];
      if (key === "non_field_errors") detail = messages[0];
      else fields[key] = messages;
    }
    // A field error with no top-level detail still needs something readable
    // in the banner, or a failed save would look like it did nothing.
    if (detail.startsWith("Request failed") && Object.keys(fields).length > 0) {
      detail = Object.values(fields)[0][0];
    }
  } catch {
    // Non-JSON error body — keep the status-based message.
  }
  return new ApiError(detail, res.status, suggestions, fields);
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  // credentials: the session cookie is what authorises these requests, and it
  // is cross-origin in production (app and API are sibling subdomains).
  const res = await fetch(`${API}/api${path}`, { signal, credentials: "include" });
  if (!res.ok) throw await toError(res);
  return res.json() as Promise<T>;
}

/** POST/PATCH/DELETE with the CSRF header Django requires. */
export async function sendJson<T>(
  method: "POST" | "PATCH" | "PUT" | "DELETE",
  path: string,
  body?: unknown,
): Promise<T | null> {
  const token = await ensureCsrfToken();
  const res = await fetch(`${API}/api${path}`, {
    method,
    credentials: "include",
    headers: {
      "X-CSRFToken": token,
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!res.ok) throw await toError(res);
  // 204 from a delete has no body to parse.
  if (res.status === 204) return null;
  return res.json() as Promise<T>;
}
