import { useReveal } from '@/hooks/useReveal';

const PROVENANCE = [
  { chip: 'Patient-provided', cls: 'border-[rgba(79,216,228,.32)] text-[#9EE7EF]', t: 'Spoken or typed by the patient, stored raw.' },
  { chip: 'Document-extracted', cls: 'border-[rgba(59,118,246,.36)] text-[#A9C2FA]', t: 'Read off an uploaded document, shown with its confidence and its original.' },
  { chip: 'AI-inferred', cls: 'border-[rgba(242,169,59,.34)] text-[#F5CE93]', t: 'Drafted by the model from the two above. Always labelled a draft.' },
  { chip: 'Doctor-verified', cls: 'border-[rgba(120,230,170,.34)] text-[#A6EBC8]', t: 'Read and signed off by a clinician. Only this is authoritative.' },
];

export function SafetyBand() {
  const ref = useReveal<HTMLElement>();
  return (
    <section
      ref={ref}
      id="safety"
      className="border-y border-hair bg-[rgba(6,10,16,.6)] py-[clamp(56px,7vw,88px)] backdrop-blur-md"
    >
      <div className="shell grid items-center gap-[clamp(28px,4vw,64px)] lg:grid-cols-2">
        <h2 className="reveal h2 max-w-[20ch]">The AI prepares. The doctor verifies. The doctor decides.</h2>
        <div className="reveal">
          <p className="lede mb-[22px]">
            MediKiosk never names a condition, never suggests a drug, never changes a dose and never makes the triage
            call. It surfaces what the patient said and what the paper says, marks what it is unsure of, and stops
            there.
          </p>
          <dl className="grid gap-2.5">
            {PROVENANCE.map((p) => (
              <div key={p.chip} className="flex flex-col gap-1 border-b border-hair pb-2.5 last:border-b-0 sm:flex-row sm:items-baseline sm:gap-3">
                <dt className="flex-none sm:min-w-[158px]">
                  <span className={`chip ${p.cls}`}>{p.chip}</span>
                </dt>
                <dd className="m-0 text-[0.9rem] text-mute">{p.t}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </section>
  );
}
