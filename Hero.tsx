import { useEffect, useRef } from 'react';
import gsap from 'gsap';
import { ArrowRight } from 'lucide-react';
import { view } from '@/lib/view';

const PANELS = [
  {
    className: 'top-[6%] -left-[6%] max-md:left-0 max-md:top-0',
    depth: 1.5,
    label: "Chief complaint, in the patient's words",
    value: 'Chest pain since this morning',
    trace: true,
  },
  {
    className: 'top-[38%] -right-[8%] max-md:right-0 max-md:top-auto max-md:bottom-[14%]',
    depth: 2.4,
    label: 'Flagged for priority review',
    value: 'Breathlessness reported with chest pain',
    note: "— routed to the doctor's priority queue",
    flag: true,
  },
  {
    className: 'bottom-[9%] left-[2%] max-md:hidden',
    depth: 1.1,
    label: 'Extracted from a lab report, 12 Mar 2026',
    value: 'HbA1c 8.2%',
    note: '— confidence 0.94',
  },
];

/** Panels drift and take a little parallax off the pointer, matching the 3D scene behind them. */
function FloatingPanels() {
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (view.reduced) return;
    const nodes = Array.from(root.current?.querySelectorAll<HTMLElement>('[data-depth]') ?? []);
    let raf = 0;
    let mx = 0;
    let my = 0;
    const tick = () => {
      mx += (view.mx - mx) * 0.06;
      my += (view.my - my) * 0.06;
      const t = performance.now() / 1000;
      nodes.forEach((n, i) => {
        const d = Number(n.dataset.depth) || 1;
        const fy = Math.sin(t * 0.6 + i * 1.7) * 3.2 * d;
        n.style.transform = `translate3d(${(-mx * 7 * d).toFixed(2)}px, ${(fy - my * 5 * d).toFixed(2)}px, 0)`;
      });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <div ref={root} aria-hidden className="relative h-[min(72svh,620px)] min-h-[380px] max-lg:mt-2 max-lg:h-[min(52svh,420px)] max-lg:min-h-[300px]">
      {PANELS.map((p) => (
        <div
          key={p.value}
          data-depth={p.depth}
          className={[
            'absolute w-max max-w-[270px] rounded-[13px] p-[11px_14px] shadow-[0_24px_60px_-34px_rgba(0,0,0,.95)]',
            'glass max-sm:max-w-[210px]',
            p.flag ? 'border-[rgba(242,169,59,.4)] bg-[rgba(30,20,8,.6)]' : '',
            p.className,
          ].join(' ')}
        >
          <div className="flex items-center gap-2 text-[0.72rem] text-dim">
            {p.flag && <span className="inline-block h-[7px] w-[7px] flex-none rounded-full bg-flag shadow-[0_0_0_4px_rgba(242,169,59,.16)]" />}
            {p.label}
          </div>
          <div className={`mt-[3px] text-[0.9rem] font-medium tracking-[-0.01em] ${p.flag ? 'text-[#FFD79A]' : 'text-ice'}`}>
            {p.value} {p.note && <span className="font-normal text-mute">{p.note}</span>}
          </div>
          {p.trace && (
            <svg className="mt-2 block opacity-85" width="176" height="22" viewBox="0 0 176 22" fill="none">
              <path
                d="M0 12h28l5-8 6 16 5-13 4 5h20l6-6 5 11 5-9 4 4h28l5-8 6 16 5-13 4 5h30"
                stroke="#4FD8E4"
                strokeOpacity=".65"
                strokeWidth="1.2"
                strokeLinejoin="round"
              />
            </svg>
          )}
        </div>
      ))}
    </div>
  );
}

export function Hero() {
  const root = useRef<HTMLElement>(null);

  useEffect(() => {
    if (view.reduced) return;
    const ctx = gsap.context(() => {
      gsap
        .timeline({ defaults: { ease: 'power3.out' } })
        .fromTo('[data-hero]', { opacity: 0, y: 22 }, { opacity: 1, y: 0, duration: 0.9, stagger: 0.11 }, 0.15)
        .fromTo('[data-depth]', { opacity: 0, scale: 0.96 }, { opacity: 1, scale: 1, duration: 0.8, stagger: 0.14 }, 0.7);
    }, root);
    return () => ctx.revert();
  }, []);

  return (
    <section ref={root} className="flex min-h-[100svh] items-center pb-16 pt-[118px]">
      <div className="shell grid w-full grid-cols-1 items-center gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,.92fr)]">
        <div>
          <div data-hero className="inline-flex items-center gap-2.5 rounded-full border border-hair bg-[rgba(12,22,33,.5)] py-[7px] pl-[9px] pr-[13px] text-[0.8rem] text-mute backdrop-blur-md">
            <span className="h-[7px] w-[7px] flex-none rounded-full bg-cyan shadow-[0_0_0_4px_rgba(79,216,228,.16)]" />
            <b className="font-medium text-ice">Smart India Hackathon</b> problem statement 26047
          </div>

          <h1 data-hero className="h1 mt-6 max-w-[14ch]">
            The history is already taken when the patient sits down.
          </h1>

          <p data-hero className="lede mt-[22px] max-w-[52ch]">
            MediKiosk interviews the patient in their own language before they reach the consultation room, reads the
            prescriptions and reports they brought with them, and hands the doctor one structured record. The doctor
            edits it, verifies it, and decides.
          </p>

          <div data-hero className="mt-[34px] flex flex-wrap gap-3">
            <a href="#start" className="btn btn-primary btn-lg group">
              Start a patient intake
              <ArrowRight size={16} className="transition-transform duration-200 group-hover:translate-x-0.5" />
            </a>
            <a href="#doctors" className="btn btn-lg">
              See the doctor view
            </a>
          </div>

          <p data-hero className="mt-[26px] flex items-center gap-2.5 text-[0.83rem] text-dim">
            <span className="h-px w-[26px] flex-none bg-[rgba(143,182,196,.26)]" />
            Nothing here is a diagnosis. Every field carries the source it came from.
          </p>
        </div>

        <FloatingPanels />
      </div>
    </section>
  );
}
