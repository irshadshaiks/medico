import { useReveal } from '@/hooks/useReveal';

const COLS = [
  {
    idx: 'The bottleneck',
    h: 'The interview collapses first',
    p: 'Under queue pressure the physician elicits history, examines, forms a diagnosis and prescribes simultaneously. Questions get skipped, comorbidities get missed, and the same three questions get asked at every visit.',
  },
  {
    idx: 'The paper',
    h: 'Records arrive unstructured',
    p: 'Patients carry prescriptions, lab reports, discharge summaries and imaging films from several providers — handwritten, in different languages, in no order. Reading them eats the consultation.',
  },
  {
    idx: 'The gap',
    h: 'Nothing feeds the national record',
    p: 'ABDM built ABHA IDs and FHIR standards, but there is no first-mile tool that captures structured history and digitises documents into that ecosystem before the encounter begins.',
  },
];

export function Problem() {
  const ref = useReveal<HTMLElement>();
  return (
    <section ref={ref} id="problem" className="section">
      <div className="shell">
        <div className="grid items-end gap-11 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,.85fr)]">
          <h2 className="reveal h2">Two minutes, one patient, and a plastic bag full of paper.</h2>
          <p className="reveal lede">
            History-taking is the highest-yield thing a physician does, and it is the first thing that gets cut when the
            queue is 400 people long. MediKiosk moves it earlier, not away.
          </p>
        </div>

        <div className="mt-[60px] grid gap-px overflow-hidden rounded-[18px] border border-hair bg-[rgba(143,182,196,.14)] md:grid-cols-3">
          {COLS.map((c) => (
            <div key={c.idx} className="reveal bg-[rgba(8,13,20,.72)] p-[clamp(22px,2.6vw,32px)] backdrop-blur-sm">
              <div className="font-display text-[0.8rem] tracking-[0.02em] text-cyan-deep">{c.idx}</div>
              <h3 className="mt-3 text-[clamp(1.15rem,1.7vw,1.4rem)] text-ice">{c.h}</h3>
              <p className="mt-3 text-[0.945rem] leading-relaxed text-mute">{c.p}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
