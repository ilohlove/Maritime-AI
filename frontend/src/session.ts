// Deliberately memory-only: no token in URLs, localStorage or sessionStorage.
export type Session = { access_token?: string; csrf_token: string; expires_at: number; user: string; transport: "bearer" | "cookie" };
let current: Session | null = null;
export const getSession = () => current;
export function setSession(value: Session | null) { current = value; }
export function expireSession() {
  current = null;
  window.dispatchEvent(new Event("maritime-session-expired"));
}
