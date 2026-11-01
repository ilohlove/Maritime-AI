import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { ShipProfile } from "./ShipProfile";
import type { Vessel } from "./api";

const stored: Vessel = {
  id: "synthetic-id",
  vessel_name: "SYNTHETIC DEMO",
  flag: "Test flag",
  field_provenance: {},
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};
function respond(data: unknown, ok = true) {
  return Promise.resolve({ ok, json: async () => data } as Response);
}

it("renders empty dashboard and navigates to actual form and planned modules", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => respond([])),
  );
  const user = userEvent.setup();
  render(<App />);
  expect(
    await screen.findByText("Your vessel workspace starts here"),
  ).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Create ship profile" }));
  expect(screen.getByLabelText("Vessel Name")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Documents" }));
  expect(screen.getByText("Coming Soon")).toBeInTheDocument();
});

it("dashboard displays real API data and toggles theme", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => respond([stored])),
  );
  const user = userEvent.setup();
  render(<App />);
  expect(await screen.findByText("SYNTHETIC DEMO")).toBeInTheDocument();
  expect(screen.getByText("Test flag")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Toggle color theme" }));
  expect(document.documentElement.dataset.theme).toBe("dark");
});

it("validates IMO and decimal input without sending invalid data", async () => {
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  const user = userEvent.setup();
  render(<ShipProfile vessel={null} onSaved={vi.fn()} />);
  await user.type(screen.getByLabelText("IMO Number"), "123");
  await user.type(screen.getByLabelText("Length Overall (m)"), "1.1234");
  await user.click(screen.getByRole("button", { name: "Create ship profile" }));
  expect(
    screen.getByText(
      "Enter a valid 7-digit IMO number, including its checksum.",
    ),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Use up to three decimal places."),
  ).toBeInTheDocument();
  expect(fetcher).not.toHaveBeenCalled();
});

it("creates a ship profile with unknowns as null", async () => {
  const fetcher = vi.fn((_url: string, _options?: RequestInit) =>
    respond(stored),
  );
  vi.stubGlobal("fetch", fetcher);
  const saved = vi.fn();
  const user = userEvent.setup();
  render(<ShipProfile vessel={null} onSaved={saved} />);
  await user.type(screen.getByLabelText("Vessel Name"), "SYNTHETIC DEMO");
  await user.click(screen.getByRole("button", { name: "Create ship profile" }));
  await waitFor(() => expect(saved).toHaveBeenCalledWith(stored));
  const payload = JSON.parse(fetcher.mock.calls[0]?.[1]?.body as string);
  expect(payload.vessel_name).toBe("SYNTHETIC DEMO");
  expect(payload.mmsi).toBeNull();
  expect(screen.getByText("Ship profile saved locally.")).toBeInTheDocument();
});

it("patches only changed fields to preserve provenance", async () => {
  const fetcher = vi.fn((_url: string, _options?: RequestInit) =>
    respond(stored),
  );
  vi.stubGlobal("fetch", fetcher);
  const user = userEvent.setup();
  render(<ShipProfile vessel={stored} onSaved={vi.fn()} />);
  await user.clear(screen.getByLabelText("Flag"));
  await user.type(screen.getByLabelText("Flag"), "Updated");
  await user.click(screen.getByRole("button", { name: "Save changes" }));
  await waitFor(() => expect(fetcher).toHaveBeenCalled());
  expect(JSON.parse(fetcher.mock.calls[0]?.[1]?.body as string)).toEqual({
    flag: "Updated",
  });
});

it("shows backend errors and retains input after a failed save", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      respond(
        {
          detail: [
            { loc: ["body", "vessel_name"], msg: "Rejected test value" },
          ],
        },
        false,
      ),
    ),
  );
  const user = userEvent.setup();
  render(<ShipProfile vessel={null} onSaved={vi.fn()} />);
  await user.type(screen.getByLabelText("Vessel Name"), "Retain this");
  await user.click(screen.getByRole("button", { name: "Create ship profile" }));
  expect(await screen.findByText("Rejected test value")).toBeInTheDocument();
  expect(screen.getByLabelText("Vessel Name")).toHaveValue("Retain this");
});

it("shows connection failure and supports retry", async () => {
  const fetcher = vi
    .fn()
    .mockRejectedValueOnce(new Error("offline"))
    .mockImplementation(() => respond([]));
  vi.stubGlobal("fetch", fetcher);
  const user = userEvent.setup();
  render(<App />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Local backend unavailable",
  );
  await user.click(screen.getByRole("button", { name: "Retry connection" }));
  expect(
    await screen.findByText("Your vessel workspace starts here"),
  ).toBeInTheDocument();
});
