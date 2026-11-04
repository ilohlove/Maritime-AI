import { getSession, expireSession } from "./session";

export type Provenance = {
  extraction_method: "user_entered" | "imported" | "ai_extracted";
  verification_status: "verified" | "unverified";
  source_document: string | null;
  last_updated: string;
};
export type Vessel = {
  id: string;
  field_provenance: Record<string, Provenance>;
  created_at: string;
  updated_at: string;
  [field: string]: unknown;
};
export class ApiError extends Error {
  constructor(
    public details: Record<string, string>,
    message: string,
  ) {
    super(message);
  }
}
export async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    const base = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
    const session = getSession();
    const headers = new Headers(options?.headers);
    if (session?.transport === "bearer" && session.access_token) headers.set("Authorization", `Bearer ${session.access_token}`);
    if (session?.transport === "cookie" && options?.method && options.method !== "GET") headers.set("X-CSRF-Token", session.csrf_token);
    response = await fetch(`${base}/api${path}`, { ...options, headers, credentials: import.meta.env.VITE_AUTH_TRANSPORT === "cookie" ? "include" : "omit", cache: "no-store" });
  } catch {
    throw new Error(
      "Cannot reach the backend. Check your connection and backend configuration, then retry. Your entries are retained.",
    );
  }
  if (!response.ok) {
    if (response.status === 401 && path !== "/auth/login") expireSession();
    const body = await response.json().catch(() => ({}));
    const details: Record<string, string> = {};
    if (Array.isArray(body.detail)) {
      for (const error of body.detail)
        details[error.loc?.at(-1) ?? "_form"] = error.msg;
    }
    throw new ApiError(
      details,
      typeof body.detail === "string"
        ? body.detail
        : typeof body.detail?.message === "string"
          ? `${body.detail.code}: ${body.detail.message}`
          : "Unable to complete request. Review the validation errors below.",
    );
  }
  return response.json() as Promise<T>;
}
export const listVessels = () => request<Vessel[]>("/vessels");
