import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthGate } from "./AuthGate";
import { getSession, setSession } from "./session";
import { request } from "./api";

const session = { access_token: "synthetic-session-token", csrf_token: "synthetic-csrf", user: "admin", transport: "bearer" as const, expires_at: Date.now()/1000 + 3600 };
const response = (data: unknown, status = 200) => Promise.resolve({ ok: status < 400, status, json: async () => data } as Response);

it("hides private workspace before sign-in and retains tokens only in memory", async () => {
  const fetcher = vi.fn(() => response(session)); vi.stubGlobal("fetch", fetcher);
  render(<AuthGate><p>Private data</p></AuthGate>);
  expect(screen.queryByText("Private data")).not.toBeInTheDocument();
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Username"), "admin");
  await user.type(screen.getByLabelText("Password"), "synthetic-password");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByText("Private data")).toBeInTheDocument();
  expect(getSession()?.access_token).toBe(session.access_token);
  expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0);
  await request("/documents");
  const options = fetcher.mock.calls.at(-1) as unknown as [string, RequestInit];
  expect(new Headers(options[1].headers).get("Authorization")).toBe("Bearer " + session.access_token);
  expect(options[1].credentials).toBe("omit");
  await user.click(screen.getByRole("button", { name: "Log out" }));
  expect(await screen.findByRole("button", { name: "Sign in" })).toBeInTheDocument();
  expect(getSession()).toBeNull();
});

it("clears private data and token on an expired API session", async () => {
  setSession(session); vi.stubGlobal("fetch", vi.fn(() => response({ detail: { code: "session_expired", message: "Sign in again." } }, 401)));
  render(<AuthGate><p>Private data</p></AuthGate>);
  await expect(request("/documents")).rejects.toThrow("session_expired");
  await waitFor(() => expect(screen.queryByText("Private data")).not.toBeInTheDocument());
  expect(screen.getByRole("alert")).toHaveTextContent("session expired");
  expect(getSession()).toBeNull();
});

it("shows failed login and rate limits without displaying the submitted password", async () => {
  vi.stubGlobal("fetch", vi.fn(() => response({ detail: { code: "rate_limited", message: "Wait a minute." } }, 429)));
  render(<AuthGate><p>Private data</p></AuthGate>);
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Username"), "admin");
  await user.type(screen.getByLabelText("Password"), "synthetic-password");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("rate_limited");
  expect(screen.getByLabelText("Password")).toHaveValue("");
  expect(screen.queryByText("Private data")).not.toBeInTheDocument();
});

it("keeps session and reports an unconfirmed logout for retry", async () => {
  setSession(session); vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("offline"))));
  render(<AuthGate><p>Private data</p></AuthGate>);
  await userEvent.click(screen.getByRole("button", { name: "Log out" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the backend");
  expect(screen.getByText("Private data")).toBeInTheDocument();
  expect(getSession()).not.toBeNull();
});

it("sends CSRF header and credentials only for configured cookie mode", async () => {
  vi.stubEnv("VITE_AUTH_TRANSPORT", "cookie");
  setSession({ ...session, access_token: undefined, transport: "cookie" });
  const fetcher = vi.fn(() => response({})); vi.stubGlobal("fetch", fetcher);
  await request("/auth/logout", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  const options = fetcher.mock.calls[0] as unknown as [string, RequestInit];
  expect(new Headers(options[1].headers).get("X-CSRF-Token")).toBe(session.csrf_token);
  expect(new Headers(options[1].headers).has("Authorization")).toBe(false);
  expect(options[1].credentials).toBe("include");
});

it("uses the configured HTTPS backend and never places tokens in the URL", async () => {
  vi.stubEnv("VITE_API_BASE_URL", "https://api.example.invalid"); setSession(session);
  const fetcher = vi.fn(() => response([])); vi.stubGlobal("fetch", fetcher);
  await request("/documents");
  expect((fetcher.mock.calls[0] as unknown as [string, RequestInit])[0]).toBe("https://api.example.invalid/api/documents");
});

it("shows a persistent disposable-storage warning before private data can be used", () => {
  setSession({ ...session, storage_warning: "DISPOSABLE SYNTHETIC TEST: data may be lost. Real AI disabled." });
  render(<AuthGate><p>Private data</p></AuthGate>);
  expect(screen.getByRole("alert")).toHaveTextContent("data may be lost");
  expect(screen.getByRole("alert")).toHaveTextContent("Real AI disabled");
});
