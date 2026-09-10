# Files to change — exact list

Unzip `medikiosk-full.zip` over your project root, or copy the files below
individually. Paths are relative to the repo root.

---

## Why you saw no change

The app could not build. Three hard failures:

1. `src/App.tsx` imported six page components that did not exist.
2. `src/lib/demoData.ts` was missing every method the rewritten `api.ts` calls
   (`userFor`, `visit`, `startIntake`, `queue`, `accessLog`, and nine others).
3. `src/sections/Hero.tsx` and `src/components/Navbar.tsx` imported `Link` from
   `react-router-dom`, while `App.tsx` uses hash routing. Two routers, one of
   them never mounted.

All three are fixed below. `react-router-dom` is now removed from
`package.json` — run `npm install` again after copying.

---

## New files (did not exist before)

| Path | What it is |
|---|---|
| `src/pages/Landing.tsx` | Marketing page; mounts the 3D scene once, fixed behind content |
| `src/pages/Login.tsx` | Sign in, with demo credentials on the page |
| `src/pages/Register.tsx` | Short registration form |
| `src/pages/PatientIntake.tsx` | Consent → complaint → questions, voice input, flag banner |
| `src/pages/DoctorQueue.tsx` | Triage queue with priority scores and reasoning |
| `src/pages/CaseFile.tsx` | Case file, per-section verification, priority breakdown |
| `src/pages/PrivacyLog.tsx` | Patient-visible access log |
| `src/sections/Features.tsx` | Four feature cards |
| `src/sections/HowItWorks.tsx` | The four-step sequence |
| `src/sections/Footer.tsx` | Footer with the synthetic-data disclaimer |
| `src/components/DocumentPanel.tsx` | Upload with every job state visible + retry |
| `src/components/PurposeGate.tsx` | Purpose-of-access dialog |
| `src/lib/auth.tsx` | Session context and the `RequireRole` guard |
| `src/main.tsx` | Entry point |
| `src/App.tsx` | Hash router |

## Replaced files

| Path | Change |
|---|---|
| `src/lib/api.ts` | Rewritten to match the real backend; 26 methods |
| `src/lib/demoData.ts` | Rewritten; every method mirrors a real API response shape |
| `package.json` | `react-router-dom` removed |

## Patched files

| Path | Change |
|---|---|
| `src/sections/Hero.tsx` | `<Link to>` → `<a href="#/">`; router import dropped |
| `src/components/Navbar.tsx` | Same |

---

## Backend files

| Path | Status |
|---|---|
| `backend/app/services/triage/priority_engine.py` | New — acuity scoring |
| `backend/app/services/privacy/access_guard.py` | New — purpose binding, break-glass, harvesting detection, export gating |
| `backend/app/models/access.py` | New — `RecordAccess`, `MisuseAlert`, `ExportReceipt` |
| `backend/app/api/privacy.py` | New — access log, sharing consent, alert review |
| `backend/app/schemas/privacy.py` | New |
| `backend/alembic/versions/0002_priority_and_access.py` | New migration |
| `backend/tests/test_priority.py` | New — 8 tests |
| `backend/tests/test_privacy.py` | New |
| `backend/app/api/documents.py` | Replaced — stall watchdog, retry endpoint |
| `backend/app/api/doctor.py` | Patched — purpose gate, rescore on read |
| `backend/app/api/abdm.py` | Patched — consent gate, watermarking |
| `backend/app/services/redflag/redflag_service.py` | Patched — calls the priority engine |
| `backend/app/models/clinical.py` | Patched — `priority_score`, `priority_factors` |
| `backend/app/schemas/clinical.py` | Patched — score fields on queue and case file |
| `backend/app/api/router.py` | Patched — privacy router registered |

---

## Run it

```bash
# Backend
cd backend
pip install -r requirements.txt      # python-multipart must be present or uploads 422
alembic upgrade head                 # 0002 is new
python -m scripts.seed_demo_data
uvicorn app.main:app --reload

# Frontend
cd ..
rm -rf node_modules package-lock.json   # react-router-dom was removed
npm install
echo "VITE_API_URL=http://localhost:8000/api/v1" > .env.local
npm run dev
```

Sign in at `http://localhost:5173/#/login` with `doctor@medikiosk.demo` /
`MediKiosk#2026`.

Without `.env.local` the frontend runs entirely on seeded demo data — useful
for checking the UI before the backend is up, and for a Vercel preview.

---

## What to look at first

**Queue ordering.** `#/doctor`. Savitri Bai, 79, sits second at score 48 with
**zero red flags** — reported as unable to carry out usual activity, almost
unable to eat, worsening, aged over 75. Under the old binary logic she was
below every flagged patient. Open her case and expand "Why this patient is
where they are" for the itemised arithmetic.

**Documents.** `#/intake` → photograph or upload. Watch the states:
`Sending… → Reading the page… → Read clearly`. Kill the backend mid-upload and
the panel reports a failure with a working retry, rather than spinning.

**Access control.** Click any queue row. The purpose dialog appears before the
record opens. Pick "Emergency access" and it demands a written reason. Then
sign in as `ravi@medikiosk.demo` and open `#/privacy` — every access is listed,
with unusual ones called out and the reason quoted back.

---

## Caveat

No network in my environment, so `npm install`, `tsc`, `pytest`, `alembic` and
`uvicorn` were never run. I verified what I could: all backend Python compiles,
all six pathway JSONs validate, every local TypeScript import resolves against
a file that exists, and I executed the priority engine and red-flag rules
directly against realistic scenarios. Expect one or two small fixes on first
`npm run dev` — most likely a Tailwind class in `index.css` that the new pages
reference (`chip-patient`, `chip-doc`, `chip-ai`, `chip-verified`, `btn-primary`,
`btn-ghost`, `glass`, `glass-quiet`, `reveal`). Those were defined in the
`index.css` from our earlier session; if you replaced that file, check they are
still there.
