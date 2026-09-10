import { useReveal } from '@/hooks/useReveal';

const STEPS = [
  {
    h: 'Language and consent',
    who: 'Patient · about 1 minute',
    p: 'The patient picks English, Hindi or Kannada. The consent screen is read aloud in that language and explains what will be collected, who sees it and how to withdraw. Nothing proceeds until it is accepted.',
  },
  {
    h: 'The interview',
    who: 'Patient · 5 to 10 minutes',
    p: 'An opening question about the problem, then a complaint-specific pathway: onset, duration, severity, associated symptoms, past history, drugs, allergies, family and personal history. Answers are stored raw, exactly as given, before anything interprets them.',
  },
  {
    h: 'The documents',
    who: 'Patient · 2 minutes',
    p: 'Old prescriptions and reports are photographed at the kiosk. OCR pulls the text, extraction pulls drugs, doses, test values and dates, each with a confidence score. The original image is kept and stays viewable forever.',
  },
  {
    h: 'The draft',
    who: 'System · seconds',
    p: 'Interview and documents merge into a chronological timeline, and a structured summary is drafted from it — complaint, history, medications, investigations, flags. It is marked a draft on every screen it appears on.',
  },
  {
    h: 'The doctor decides',
    who: 'Doctor · under a minute to review',
    p: 'The case appears in a queue, sorted by flag. The doctor reads, corrects anything wrong, accepts section by section, adds clinical notes and verifies. Only then does the record become authoritative, and every change is in the audit trail.',
  },
];

export function HowItWorks() {
  const ref = useReveal<HTMLElement>({ stagger: 0.07 });
  return (
    <section ref={ref} id="how" className="section">
      <div className="shell">
        <div className="grid items-end gap-11 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,.85fr)]">
          <h2 className="reveal h2">Five steps, and the doctor is in none of the first four.</h2>
          <p className="reveal lede">A patient arrives, registers, and is directed to a kiosk. What follows runs on its own.</p>
        </div>

        <ol className="mt-16 list-none border-t border-hair p-0">
          {STEPS.map((s, i) => (
            <li
              key={s.h}
              className="reveal grid grid-cols-1 items-start gap-[clamp(18px,3vw,44px)] border-b border-hair py-[clamp(26px,3.4vw,40px)] md:grid-cols-[64px_minmax(0,.9fr)_minmax(0,1fr)]"
            >
              <div className="pt-[3px] font-display text-[1.05rem] tracking-[-0.02em] text-cyan-deep">Step {i + 1}</div>
              <div>
                <h3 className="text-[clamp(1.15rem,1.7vw,1.4rem)] text-ice">{s.h}</h3>
                <div className="mt-2.5 text-[0.8rem] text-dim">{s.who}</div>
              </div>
              <p className="text-[0.95rem] leading-relaxed text-mute">{s.p}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
