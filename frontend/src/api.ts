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
    response = await fetch(`/api${path}`, options);
  } catch {
    throw new Error(
      "Cannot reach the local backend. Check that it is running, then retry. Your entries are retained.",
    );
  }
  if (!response.ok) {
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
        : "Unable to save. Review the validation errors below.",
    );
  }
  return response.json() as Promise<T>;
}
export const listVessels = () => request<Vessel[]>("/vessels");
