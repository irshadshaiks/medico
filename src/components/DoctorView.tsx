import { ArrowRight } from 'lucide-react';
import { useState } from 'react';
import { useReveal } from '@/hooks/useReveal';

const SUMMARY = [
  { lab: 'Complaint', body: <><strong className="font-medium text-ice">Central chest pain, 6 hours</strong>, radiating to the left arm, with breathlessness on exertion.</> },
  { lab: 'History', body: <>Type 2 diabetes noted in a 2025 prescription. Hypertension on the same script.</> },
  { lab: 'Medications', body: <><strong className="font-medium text-ice">Metformin 500&nbsp;mg</strong> twice daily, <strong className="font-medium text-ice">Amlodipine 5&nbsp;mg</strong> once daily.</> },
  { lab: 'Labs', body: <><strong className="font-medium text-ice">HbA1c 8.2%</strong> on 12 Mar 2026.</> },
];

export function DoctorView() {
  const ref = useReveal<HTMLElement>();
  // Local only: shows the state change an accept produces, nothing is persisted here.
  const [accepted, setAccepted] = useState(false);

  return (
    <section ref={ref} id="doctors" className="section">
      <div className="shell">
        <div className="mt-14 grid items-center gap-[clamp(32px,4vw,60px)] lg:grid-cols-[minmax(0,.82fr)_minmax(0,1.18fr)]">
          <div>
            <h2 className="reveal h2">The doctor opens one screen, not fourteen pages.</h2>
            <p className="reveal lede mt-[22px]">
              The dashboard is dense on purpose. Queues sorted by clinical priority, the original document beside its
              extraction, the timeline, and a summary that is clearly a draft until a human says otherwise.
            </p>
            <div className="reveal mt-[34px] flex flex-wrap gap-3">
              <a href="#login" className="btn btn-primary group">
                Log in as a doctor
                <ArrowRight size={16} className="transition-transform duration-200 group-hover:translate-x-0.5" />
              </a>
              <a href="#safety" className="btn">Read the safety model</a>
            </div>
          </div>

          <div className="reveal overflow-hidden rounded-[20px] border border-hairStrong bg-gradient-to-b from-[rgba(11,19,30,.88)] to-[rgba(5,9,14,.82)] shadow-[0_60px_120px_-60px_rgba(0,0,0,1)] backdrop-blur-xl backdrop-saturate-150">
            <div className="flex items-center gap-2.5 border-b border-hair bg-white/[.012] px-4 py-3">
              <span className="h-[7px] w-[7px] rounded-full bg-cyan shadow-[0_0_0_4px_rgba(79,216,228,.16)]" />
              <span className="text-[0.82rem] text-mute">Outpatient queue — General Medicine, Tuesday</span>
              <span className="flex-1" />
              <span className="text-[0.82rem] text-mute">Dr. A. Menon</span>
            </div>

            <div className="flex flex-wrap border-b border-hair">
              {[
                { n: '3', l: 'Priority', hot: true },
                { n: '7', l: 'Needs review' },
                { n: '21', l: 'Routine' },
              ].map((q, i) => (
                <div key={q.l} className={`min-w-[100px] flex-1 px-4 py-3.5 text-[0.8rem] text-dim ${i ? 'border-l border-hair' : ''}`}>
                  <b className={`mb-[3px] block font-display text-[1.5rem] font-medium tracking-[-0.03em] ${q.hot ? 'text-flag' : 'text-ice'}`}>
                    {q.n}
                  </b>
                  {q.l}
                </div>
              ))}
            </div>

            <div className="p-4">
              <div className="flex items-center gap-3 rounded-xl border border-[rgba(242,169,59,.35)] bg-[rgba(242,169,59,.055)] px-3.5 py-3">
                <div className="grid h-[34px] w-[34px] flex-none place-items-center rounded-[9px] border border-hair bg-gradient-to-br from-[rgba(79,216,228,.22)] to-[rgba(59,118,246,.22)] text-[0.78rem] text-ice">
                  RK
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-[0.9rem] font-medium text-ice">Ravi Kumar, 54</div>
                  <div className="mt-0.5 text-[0.775rem] text-dim">Chest pain since 06:00 · intake completed 11 minutes ago</div>
                </div>
                <span className="whitespace-nowrap rounded-md border border-[rgba(242,169,59,.4)] bg-[rgba(242,169,59,.1)] px-2.5 py-1 text-[0.72rem] text-[#FFD79A]">
                  Breathlessness
                </span>
              </div>

              <div className="mt-3.5 rounded-xl border border-hair p-3.5">
                <div className="flex flex-wrap items-center gap-2.5">
                  <span className="text-[0.85rem] font-medium text-ice">Clinical summary</span>
                  {accepted ? (
                    <span className="rounded-md border border-[rgba(120,230,170,.5)] px-2 py-[3px] text-[0.7rem] text-[#A6EBC8]">
                      Doctor-verified
                    </span>
                  ) : (
                    <span className="rounded-md border border-dashed border-[rgba(242,169,59,.5)] px-2 py-[3px] text-[0.7rem] text-[#F5CE93]">
                      Draft — not verified
                    </span>
                  )}
                </div>
                <ul className="mt-3 grid list-none gap-2.5 p-0">
                  {SUMMARY.map((s) => (
                    <li key={s.lab} className="flex items-baseline gap-2.5 text-[0.85rem] leading-relaxed text-mute">
                      <span className="min-w-[74px] flex-none text-[0.75rem] text-dim">{s.lab}</span>
                      <span>{s.body}</span>
                    </li>
                  ))}
                </ul>
                <div className="mt-4 flex flex-wrap gap-[7px]">
                  <span className="chip border-[rgba(79,216,228,.32)] text-[#9EE7EF]">Complaint — patient</span>
                  <span className="chip border-[rgba(59,118,246,.36)] text-[#A9C2FA]">Drugs — 2025 prescription</span>
                  <span className="chip border-[rgba(59,118,246,.36)] text-[#A9C2FA]">HbA1c — lab report</span>
                  <span className="chip border-[rgba(242,169,59,.34)] text-[#F5CE93]">Summary — drafted</span>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 border-t border-hair px-4 py-3.5">
              <button
                type="button"
                onClick={() => setAccepted((v) => !v)}
                className="rounded-[9px] border border-transparent bg-cyan px-3.5 py-2 text-[0.8rem] font-semibold text-[#02171B] transition-colors hover:bg-cyan-soft"
              >
                {accepted ? 'Section accepted' : 'Accept section'}
              </button>
              <button type="button" className="rounded-[9px] border border-hair px-3.5 py-2 text-[0.8rem] text-mute transition-colors hover:border-hairStrong hover:bg-[rgba(143,182,196,.07)] hover:text-ice">
                Edit
              </button>
              <button type="button" className="rounded-[9px] border border-hair px-3.5 py-2 text-[0.8rem] text-mute transition-colors hover:border-hairStrong hover:bg-[rgba(143,182,196,.07)] hover:text-ice">
                Reject
              </button>
              <span className="ml-auto text-[0.75rem] text-dim">Every action written to the audit trail</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
