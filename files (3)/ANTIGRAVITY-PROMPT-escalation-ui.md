# Prompt for Antigravity — escalation UI

The backend is built and in `escalation-files.zip`. This prompt covers only the
frontend. Commit first: `git add -A && git commit -m "before escalation UI"`.

---

## THE PROMPT

Add the emergency-escalation user interface to the MediKiosk frontend. The
backend already exists — do not write backend code, and do not modify any file
under `backend/`.

### Rule zero — do not modify

```
src/pages/DoctorQueue.tsx
src/pages/CaseFile.tsx
src/pages/PrivacyLog.tsx
src/components/PurposeGate.tsx
src/components/DocumentPanel.tsx
src/lib/auth.tsx
```

You may extend `src/lib/api.ts`, `src/lib/demoData.ts`, `src/App.tsx` and
`src/pages/PatientIntake.tsx` additively. No refactors, no renames, no
reformatting of code you are not changing. If something seems to need a
refactor, stop and say so rather than doing it.

### Background — what this is for

A patient having an emergency often doesn't know it, and joins the outpatient
queue anyway. The backend now asks one danger question before the clinical
interview starts. If the answer matches one of six escalation rules, intake
halts and the patient must be sent to the Emergency counter immediately.

The interface has one job in that moment: get someone who may be very unwell to
walk to the right counter, fast, possibly while frightened, possibly unable to
read well.

### 1. Endpoints available

```
POST /patient/visits/{visit_id}/safety-screen
     -> { conversation_id, question: { id, presented_text, answer_type, options } }

POST /patient/visits/{visit_id}/safety-screen/answer
     body: { conversation_id, question_id, text, respondent, attendant_relationship }
     -> { escalated, id, instruction, destination, clinically_signed_off }

GET  /staff/escalations
     -> [{ id, visit_id, patient_name, patient_age, rule_id, staff_label,
            destination, evidence, clinically_signed_off, raised_at, waiting_seconds }]

POST /staff/escalations/{id}/acknowledge
     body: { outcome, note }
     outcome is one of: escorted_to_emergency | assessed_remained_in_opd |
                        patient_declined | patient_not_found
```

Add these to `api.ts` following the existing patterns exactly, including the
`DEMO_MODE` branch and matching `demo.*` methods.

### 2. Change the intake order

In `PatientIntake.tsx`, add a `safety` stage **before** `consent`:

```
safety -> consent -> complaint -> questions -> done
```

On mount, once the visit exists, call `safety-screen` and render the question.
The patient cannot reach consent until they answer it. This ordering is the
whole point — the danger question runs before we know anything else.

If the answer returns `escalated: true`, switch to a new terminal stage and
render `<EscalationScreen />`. Do not continue to consent. Do not offer a way
back into the interview.

### 3. `src/components/EscalationScreen.tsx`

This is the most important screen in the product and the least like the rest of
it. Ignore the existing dark glassmorphic aesthetic here.

- Full viewport. Nothing else on screen — no navbar, no footer, no progress bar,
  no back link.
- Solid high-contrast background, not glass, not translucent. This has to be
  readable on a scratched kiosk screen under a fluorescent tube, by someone who
  may be sweating and frightened.
- The `instruction` text from the API at the largest size the viewport allows —
  target 32px minimum on mobile. One instruction, nothing else competing.
- The `destination` below it, also large.
- A single large button: "Show this to a staff member", which enlarges the
  instruction further and displays the visit token number.
- **No timer, no countdown, no auto-redirect, no dismiss control.** The patient
  must not be able to tap past this by accident, and it must not disappear on
  its own.
- When `clinically_signed_off` is `false`, render a small, low-contrast line at
  the very bottom: "Demonstration protocol — pending clinical approval." Small
  because it must not compete with the instruction, present because nobody
  should mistake a draft protocol for an approved one.
- Announce it to screen readers: `role="alert"`, `aria-live="assertive"`.

**Never add any text explaining what the symptoms might mean.** No "this could
be serious", no condition name, no urgency language beyond the instruction the
API returned. Render `instruction` verbatim; do not template around it.

### 4. Attendant mode

On the safety screen and throughout intake, add a small persistent toggle:
"I am answering for someone else."

When on, send `respondent: "attendant"` and prompt once for the relationship
(son, daughter, spouse, other). Show a quiet persistent indicator so it is
obvious the mode is active. The backend tags those answers
`ATTENDANT-REPORTED`, which the doctor sees.

Keep the toggle small and unobtrusive. Most patients answer for themselves and
should not have to think about it.

### 5. `src/pages/StaffBoard.tsx` — new route `#/staff`

The triage desk screen. Assume it is on a wall monitor nobody is sitting at.

- Poll `GET /staff/escalations` every 5 seconds.
- Each alert: patient name, age, `staff_label`, destination, and a live "waiting
  Xm Ys" counter from `waiting_seconds` that keeps climbing.
- Quote the patient's own words from `evidence` — that is what tells a nurse
  whether to run.
- Order oldest first. Longest-waiting alert at the top, always.
- Escalate the visual state as time passes: after 2 minutes the card intensifies,
  after 5 minutes it is unmissable from across a room.
- Acknowledging requires choosing one of the four outcomes. **Do not default the
  selection** — the outcome data is how the false-positive rate gets measured,
  and a pre-selected default will just be clicked through.
- Empty state: "No alerts." Calm, not celebratory.
- No sound by default. Add a mute-able toggle, off initially — an alarm nobody
  can silence gets unplugged.

Guard the route with `RequireRole role={['doctor','admin']}`.

### 6. Tests / verification

Before saying you are done, confirm:

1. The safety screen appears before consent, and cannot be skipped
2. Answering "None of these" proceeds normally to consent
3. Answering "Chest pain right now" plus "Sweating heavily" shows the escalation
   screen and ends intake
4. The escalation screen has no dismiss, no timer, no back link
5. `#/staff` shows the alert, the counter climbs, acknowledging clears it
6. Attendant mode sends `respondent: "attendant"`
7. `npm run build` passes
8. Every existing screen — queue, case file, privacy log, documents — works
   unchanged

List every file you created and the exact diff for every file you modified.

### What NOT to build

- No condition names or explanations on the escalation screen
- No countdown, auto-dismiss, or auto-redirect
- No new backend code
- No changes to the doctor queue, case file, privacy log or document panel
- No refactoring of anything currently working
