# MediKiosk — Backend

Pre-consultation patient case-taking API for SIH26047.

**AI prepares. The doctor verifies. The doctor decides.** No endpoint in this
service diagnoses, prescribes, or makes a clinical decision. That constraint is
enforced in code, not just in documentation — see [Safety architecture](#safety-architecture).

---

## Stack

| Layer | Choice |
|---|---|
| Runtime | Python 3.11 |
| Framework | FastAPI + Pydantic v2 |
| ORM | SQLAlchemy 2.0 (async, `asyncpg`) |
| Migrations | Alembic (sync, `psycopg2`) |
| Database | PostgreSQL 15 |
| Auth | JWT (HS256), bcrypt, refresh rotation |
| AI | Gemini, behind an abstraction, defaulting to an offline mock |
| OCR | Tesseract (eng + hin + kan), defaulting to an offline mock |
| Storage | S3, or local disk |

---

## Run it

### Docker (recommended)

```bash
cd backend
docker compose up --build
```

That migrates, seeds the four demo scenarios, and serves on
<http://localhost:8000>. Docs at `/docs`.

### Without Docker

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # works as-is against a local Postgres
alembic upgrade head
python -m scripts.seed_demo_data
uvicorn app.main:app --reload
```

### Demo logins

Password for all accounts: `MediKiosk#2026`

| Account | Scenario |
|---|---|
| `doctor@medikiosk.demo` | Doctor dashboard, four patients in the queue |
| `ravi@medikiosk.demo` | Chest pain — fires two red flags, sits at the top of the queue |
| `anjali@medikiosk.demo` | Headache with a visual symptom, plus an abnormal haemoglobin |
| `kumar@medikiosk.demo` | Routine follow-up — deliberately fires nothing |
| `lakshmi@medikiosk.demo` | Document-heavy chronic case |

Every record is synthetic.

---

## It runs with no API keys

Every provider defaults to an offline adapter:

```
AI_PROVIDER=mock  OCR_PROVIDER=mock  STORAGE_PROVIDER=local  ABDM_PROVIDER=mock
```

The full intake → red flag → summary → verify → export flow works with no
network access and no credentials. To use real providers, set
`AI_PROVIDER=gemini` with `GEMINI_API_KEY`, or `OCR_PROVIDER=tesseract`
(the binary is already in the Docker image).

If a real provider is configured but unavailable, the factory logs the reason
and falls back to the mock rather than refusing to boot.

---

## Safety architecture

Four decisions carry the clinical-safety weight.

**1. The safety preamble cannot be bypassed.**
`BaseAIService.complete()` owns the preamble, timeout, retries and fallback.
Adapters implement only the raw `_call()` to their vendor. A new provider
therefore cannot ship without the constraints attached, and
`test_safety_preamble_is_attached_to_every_call` asserts it.

**2. Clinical logic is deterministic; the model only phrases.**
Question order lives in `app/services/questioning/pathways/*.json`. Turning an
answer into structured booleans is keyword matching in `structure_answer()`.
The LLM is used for one thing: making a question sound natural in Hindi or
Kannada. A model outage makes MediKiosk read worse; it cannot make it ask the
wrong clinical question.

**3. Red flags are rule predicates, never model output.**
`app/services/redflag/rules.py` holds 18 explicit predicates. Each stores the
`rule_id` and the patient's own quoted words, so "why is this person top of the
queue" always has a specific answer. `test_no_rule_uses_diagnostic_language`
asserts on the exact strings that no rule contains diagnostic or urgency
wording.

**4. Doctor edits never overwrite AI drafts.**
`SummarySection.ai_body` and `.doctor_body` coexist permanently. Every accept,
edit and reject writes an immutable `DoctorVerification` row with before and
after. Finalising is refused while any section is still an untouched draft.

Every clinical fact carries a `Provenance`: `PATIENT-PROVIDED`,
`DOCUMENT-EXTRACTED`, `AI-INFERRED` or `DOCTOR-VERIFIED`.

---

## Layout

```
app/
  core/          config, security, errors, logging, rate limit, prompts
  db/            declarative base, async session
  models/        21 tables across user / clinical / document / record
  schemas/       Pydantic request and response models
  api/           auth, patient, documents, doctor, abdm, admin
  services/
    ai/          base (safety + retry) · gemini · mock · factory
    ocr/         base · tesseract · mock · factory
    storage/     base · local · s3 · factory
    speech/      browser passthrough, cloud slot
    abdm/        base · mock · empty real stub
    questioning/ schema · pathway_engine · complaint_classifier · pathways/*.json
    redflag/     rules (18 predicates) · redflag_service
    conversation_service · document_service · timeline_service
    summary_service · audit_service
alembic/versions/0001_initial.py
scripts/seed_demo_data.py
tests/
```

`app/core/prompts.py` holds every prompt the application sends. Centralising
them is deliberate — it means the anti-diagnosis and anti-fabrication rules are
reviewable in one file.

---

## API

All routes under `/api/v1`.

**Auth** — `POST /auth/register` · `/auth/login` · `/auth/refresh` ·
`/auth/logout` · `GET /auth/me`

**Patient** — `POST /patient/visits` · `GET /patient/visits/current` ·
`POST /patient/visits/{id}/consent` · `POST /patient/visits/{id}/intake` ·
`GET /patient/conversations/{id}` · `GET /patient/conversations/{id}/next-question` ·
`POST /patient/conversations/{id}/answer` · `GET /patient/conversations/{id}/red-flags`

**Documents** — `POST /patient/visits/{id}/documents` ·
`GET /documents/{id}` · `GET /documents/{id}/file` · `GET /documents/{id}/extraction`

**Doctor** — `GET /doctor/queue` · `GET /doctor/visits/{id}` ·
`POST /doctor/visits/{id}/summary` · `POST /doctor/summaries/{id}/verify` ·
`POST /doctor/summaries/{id}/finalize` · `GET /doctor/patients/{id}/timeline` ·
`GET /doctor/audit/{entity_type}/{entity_id}`

**ABDM (simulated)** — `POST /abdm/link-abha` · `GET /abdm/export/{visit_id}` ·
`GET /abdm/status`

**Ops** — `GET /health` (liveness, no DB) · `GET /health/ready` (503 when the
database is unreachable)

`GET /doctor/visits/{id}` returns the whole case file — visit, patient, red
flags, summary, timeline, documents — in one round trip, because the doctor's
screen needs all of it at once and a waterfall of six requests would be visible.

### Resuming an interrupted intake

`GET /patient/conversations/{id}/next-question` doubles as the resume endpoint.
The cursor lives in the database, so a kiosk that reloads mid-intake continues
from the same question. Answers accept a `client_token`, making a retried
submission idempotent rather than duplicating a response.

---

## Tests

```bash
pytest
```

Covers pathway ordering and conditional nodes, keyword structuring (including
transliterated Hindi and Kannada), red-flag triggers *and* non-triggers,
diagnostic-language assertions on rule copy, provider factory resolution,
timeout/retry fallback, JSON recovery from fenced or prefixed model output,
complaint routing with ambiguity falling back to generic, and upload validation
against content-type spoofing.

The non-trigger tests matter as much as the triggers: a queue where everything
is priority is a queue with no priority in it.

---

## Notes and known limits

- **OCR and extraction run as FastAPI background tasks, not Celery.** The work
  takes seconds, job state already lives in `DocumentExtraction.ocr_status`
  where the client polls it, and a broker is one more thing to keep alive.
  Worth revisiting if throughput ever matters.
- **ABDM is simulated and says so.** Mock ABHA numbers carry a `DEMO-` prefix
  so they cannot be mistaken for real identifiers, every response includes
  `simulated: true`, and `RealAbdmAdapter` is deliberately empty rather than
  half-implemented.
- **Medication deduplication is rule-based**, not fuzzy-matched. Brand-versus-
  generic names will not merge.
- **Document-derived red flags are not implemented.** An abnormal lab value
  does not currently feed the rules engine; only conversation answers do.
