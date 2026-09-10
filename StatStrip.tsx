import { useReveal } from '@/hooks/useReveal';

const STATS = [
  { n: '4,000–10,000', t: 'Outpatients a day in a tertiary government hospital' },
  { n: '2–5 min', t: 'Time a physician actually gets per patient' },
  { n: '70–80%', t: 'Of diagnoses reachable from a well-taken history alone' },
  { n: 'English · हिंदी · ಕನ್ನಡ', t: 'Spoken and written at the kiosk, switchable mid-interview' },
];

export function StatStrip() {
  const ref = useReveal<HTMLElement>({ stagger: 0.07 });
  return (
    <section ref={ref} className="border-y border-hair bg-[rgba(6,10,16,.5)] backdrop-blur-md">
      <div className="mx-auto grid max-w-shell grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        {STATS.map((s) => (
          <div key={s.n} className="reveal border-t border-hair px-[clamp(18px,2.4vw,32px)] py-[30px] first:border-t-0 sm:border-l sm:first:border-l-0 lg:border-t-0">
            <div className="font-display text-[clamp(1.5rem,2.4vw,2.05rem)] leading-none tracking-[-0.035em] text-ice">
              {s.n}
            </div>
            <div className="mt-2.5 max-w-[26ch] text-[0.83rem] leading-relaxed text-dim">{s.t}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
