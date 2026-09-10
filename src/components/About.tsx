import { useReveal } from '@/hooks/useReveal';

const SPECS = [
  ['Problem statement', 'SIH 26047 — Patient Case-Taking Software'],
  ['Patient interface', 'React, Vite, TypeScript, Tailwind'],
  ['3D and motion', 'Three.js, React Three Fiber, GSAP'],
  ['Backend', 'FastAPI, Pydantic, SQLAlchemy'],
  ['Database', 'PostgreSQL, Alembic migrations'],
  ['OCR', 'Tesseract, swappable for Document AI'],
  ['Language model', 'Behind an AIService interface'],
  ['Deployment', 'Cloud Run, Cloud SQL, Cloud Storage'],
];

export function About() {
  const ref = useReveal<HTMLElement>();
  return (
    <section ref={ref} id="about" className="section">
      <div className="shell grid gap-[clamp(30px,4vw,64px)] lg:grid-cols-[minmax(0,1fr)_minmax(0,.85fr)]">
        <div>
          <h2 className="reveal h2">Built for the first mile of Indian public healthcare.</h2>
          <p className="reveal lede mt-[22px]">
            Government hospitals run some of the densest outpatient loads in the world, with consultation times among
            the shortest measured anywhere. MediKiosk is a pre-consultation intake platform for exactly that setting:
            cheap to run, offline-tolerant, multilingual, and designed so the clinician stays the decision-maker at
            every step.
          </p>
          <p className="reveal lede mt-[18px]">
            It is built as a sequence of independent modules — auth and consent, the questioning engine, the document
            pipeline, the timeline, the verification workflow — each with its own tests, so the system can be assembled
            and audited a piece at a time.
          </p>
        </div>
        <div className="reveal">
          <dl className="grid overflow-hidden rounded-2xl border border-hair">
            {SPECS.map(([k, v]) => (
              <div key={k} className="flex flex-col justify-between gap-1 border-b border-hair px-4 py-3.5 text-[0.86rem] last:border-b-0 sm:flex-row sm:gap-5">
                <dt className="text-dim">{k}</dt>
                <dd className="m-0 text-ice sm:text-right">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </section>
  );
}
