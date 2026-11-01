# Task 01 UI review

The existing application was retrieved from remote `feature/initial-foundation`,
commit `1ae911d8e8fd65963bf6ed9e06dbe16ff7bee28c`, into this initially empty checkout.
Preview preparation is on `feature/ui-preview`. Task 02 has not started.

## Access limitation

The attached environment reports no capabilities, and this session exposes no
preview or port-forwarding tool. There is no supported authenticated preview URL
to provide. `http://127.0.0.1:5173` is running inside the cloud environment only;
opening that address on a phone points to the phone itself. No deployment or
public tunnel was made.

The immediate visual alternative is the captured screenshots of the real running
application (Android light/dark Dashboard, full Ship Profile, desktop Dashboard).
These are screenshots, not an interactive preview. For interactive review, use
the synthetic launcher on a computer on the phone's Wi-Fi, as documented in the
README. A source ZIP is supplied alongside the screenshots for this purpose.

## Configuration

- FastAPI remains bound to `127.0.0.1:8000`.
- React/Vite runs at `127.0.0.1:5173` by default. An explicit `--host` enables a
  network bind only when an exact `--origin` is supplied.
- Relative `/api` calls use the existing Vite proxy, keeping browser requests
  on the frontend origin. Backend write protection retains explicit origins.
- `.preview-synthetic/maritime.db` is ignored and separate from operational data.
- The launcher seeds synthetic particulars once and retains later edits.
- No AI service, real vessel identifiers, documents, or operational data is used.

## Verification

- Backend: 29 tests passed, including SQLite persistence across app restart.
- Frontend: 7 unit tests passed; TypeScript and Vite production build passed.
- Dependency review: npm audit reported zero vulnerabilities.
- Chromium: both browser tests passed, including Pixel 7 touch emulation.
- Verified Dashboard, Ship Profile, field edits, invalid MMSI rejection, save,
  Dashboard updates, reload and persisted field values; no horizontal page overflow.
- Captured real UI screenshots with no browser page errors.
- Stopped and restarted both preview servers and checked the same saved profile
  remained in SQLite without re-seeding or resetting edits.

The original smoke test's dimensions were made internally consistent so it also
works on the seeded preview. Its initial failure correctly rejected a length
overall shorter than the existing length between perpendiculars.

Pixel 7 emulation is not a test on a physical Android device. Android phone
access and an authenticated cloud preview URL could not be verified here.
Windows validation was not run in this session.

## Phone acceptance steps

1. Open the local-network URL printed by the synthetic launcher.
2. Confirm Dashboard shows **SYNTHETIC PREVIEW VESSEL — TEST DATA**.
3. Tap **View / edit ship profile** (or **Ship Profile** in the horizontal navigation).
4. Change a field to another synthetic value, scroll down, and tap **Save changes**.
5. Confirm **Ship profile saved locally.** and return to Dashboard.
6. Reload, reopen Ship Profile, and confirm the saved value.
7. Optionally stop/restart the launcher and repeat step 6.

Review and approval remain pending. No further feature work is authorized by this preview.
