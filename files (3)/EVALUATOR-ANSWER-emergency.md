# Answer to the evaluator: "it won't work for emergencies"

Use this as your response. It concedes the real point, rejects the wrong one,
and shows the change.

---

## The short version

> You were right, and the problem was worse than you described.
>
> MediKiosk is an OPD system. A patient in cardiac arrest goes to Casualty, not
> to the outpatient queue, and no intake software changes that.
>
> But the dangerous patient isn't the one who knows it's an emergency. It's the
> one who **doesn't** — and takes an OPD token anyway. Our own demo patient is
> exactly that person: Ravi, 54, diabetic, chest heaviness radiating to his left
> arm, sweating. He is the person who dies in an OPD line, and he had taken a
> token for General Medicine.
>
> Our system detected him correctly and then did something nearly useless with
> that: moved him from position 40 to position 1. Still in the queue. Still
> waiting. Still in the wrong department.
>
> So we changed what happens. The first thing every patient now sees, before
> the complaint is even recorded, is a ten-second danger screen. If it matches,
> the interview stops mid-question, the screen tells them to go to the Emergency
> counter, and the triage desk alarms with their token number.
>
> The system's job in an emergency isn't to interview anyone. It's to work out
> in ten seconds that this person shouldn't be in the queue at all, and get them
> out of it.

---

## What changed, concretely

**A safety screen runs before the complaint.** One multiple-choice question,
ten options, about what is happening *right now* — chest pain, breathing
difficulty, sudden weakness, facial droop, a fit today, confusion, bleeding that
won't stop, throat swelling. Asked before the pathway is chosen, before any
clinical question, before we know anything about the patient.

Its wording is never rephrased by the language model, unlike every other
question in the system. An LLM softening "right now" would quietly defeat the
control.

**Escalation is a different thing from a red flag.** We now have two engines
with deliberately different sizes:

| | Red flags | Escalations |
|---|---|---|
| Count | 18 rules | **6 rules** |
| Effect | Moves up the OPD queue | Stops intake, sends to Casualty, alarms triage desk |
| Tuned to | Catch anything a doctor would want sooner | Almost never fire |

That asymmetry is the design. A false escalation costs a nurse a few minutes.
Over-trigger and Casualty floods, staff stop believing the alarm, and someone
disables the feature by the end of the first week. **A safety system that gets
switched off protects nobody.**

Verified behaviour:

```
MUST ESCALATE
  Chest pain now + sweating            -> esc_chest_pain_active
  Sudden facial droop                  -> esc_stroke_pattern
  Breathless at rest now               -> esc_breathing_difficulty
  Fit today                            -> esc_altered_consciousness
  Bleeding won't stop                  -> esc_active_bleeding
  Throat swelling                      -> esc_airway_swelling

MUST NOT ESCALATE
  Ravi: exertional chest pain, settled -> no escalation (red flag instead)
  Stable diabetes follow-up            -> no escalation
  Fever + cough, 3 days                -> no escalation
  Headache 6 weeks, blurred vision     -> no escalation
  Fainted last week                    -> no escalation
  ALL 14 red-flag keys set true        -> no escalation
```

That last line is the one to point at. The two engines share one facts dict,
so every escalation key is namespaced `esc_`. A red-flag key **cannot** reach an
escalation rule, and a test asserts it.

Note what happens to Ravi: his pain has settled, so he is a red flag at queue
position 1, not an escalation. The same man answering "chest pain right now"
plus "sweating" is escalated instead. The distinction is *present-tense danger*,
not severity of history.

**Attendant mode.** A patient too unwell, too elderly or too distressed to use
the kiosk almost always has family beside them. They can answer on the patient's
behalf, and every such answer is tagged `ATTENDANT-REPORTED` rather than
`PATIENT-PROVIDED` — a son describing his mother's symptoms is genuinely less
reliable than the mother, and the doctor must see which it was. This is also the
accessibility answer for the low-literacy and elderly users the problem
statement names.

**Fail open, always.** If escalation evaluation throws, times out, or the
database is unreachable, the patient continues intake normally and the red-flag
engine still runs. Completing intake is never a precondition for being seen. If
you can construct a scenario where our software stands between a patient and a
doctor, that is a defect worse than the one we just fixed.

**The alarm cannot clear itself.** An unacknowledged escalation never expires. A
named staff member must acknowledge it and record what they did — escorted,
assessed and kept in OPD, patient declined, patient not found. An alert that
times out silently looks calm on screen while nobody has gone to fetch anyone.
Those outcomes also give us a measured false-positive rate instead of a guess.

---

## What we are NOT claiming

Say this before he asks.

**These six rules are not a validated protocol.** We drafted them from published
emergency-presentation criteria. Every rule ships with `signed_off = False` and
a named-clinician field that is empty, and a test asserts that none of them
claims sign-off. In production the service **refuses to escalate on an unsigned
rule**, so an unreviewed pattern cannot reach a real patient. The hospital owns
this protocol; we only encode it.

**This does move a line we previously drew.** We have been saying "the AI never
decides urgency." A rule that says *stop, see someone now* edges toward that.
Our defence: the rule is not deciding clinical urgency, it is executing a
hospital protocol that says this pattern of reported symptoms goes to the front
desk rather than the queue. The patient is told **where to go and never what
might be wrong** — a test asserts the instruction contains no condition name, no
"could be", no "serious". Panic doesn't help anyone walk forty metres to
Casualty.

**We have not solved pre-hospital emergencies.** Someone collapsing at home is
an ambulance problem. Nothing here addresses that, and we are not pretending it
does.

**A patient can lie or misjudge.** Someone who taps "none of these" while having
an infarct is not caught by this screen. It reduces a risk; it does not remove
one.

---

## If he pushes further

**"You're still relying on the patient to self-report."** Yes. So does the
triage nurse at the counter, and so does every symptom checker in clinical use.
The difference is that our screen reaches every patient in the queue in ten
seconds, where a nurse reaches a fraction of them. And attendant mode covers the
patient who cannot answer at all.

**"What if the kiosk is down?"** The hospital works exactly as it does today.
That is the fail-open guarantee, and it is the reason we refuse to make intake a
prerequisite for being seen.

**"Six rules isn't enough coverage."** Coverage is not the objective; a believed
alarm is. We would rather add a seventh rule after measuring outcome data from
the six than ship twenty and have the desk ignore all of them. The
acknowledgement outcomes exist precisely to make that a data decision.
