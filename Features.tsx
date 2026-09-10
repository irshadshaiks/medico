import { AlertTriangle, FileText, GitBranch, MessageSquare, Mic, Share2, ShieldCheck } from 'lucide-react';
import type { ReactNode } from 'react';
import { useReveal } from '@/hooks/useReveal';

function Icon({ children, tone = 'cyan' }: { children: ReactNode; tone?: 'cyan' | 'flag' }) {
  return (
    <div
      className={`mb-4 grid h-[34px] w-[34px] place-items-center rounded-[10px] border border-hair ${
        tone === 'flag' ? 'bg-[rgba(242,169,59,.08)] text-flag' : 'bg-[rgba(79,216,228,.07)] text-cyan'
      }`}
    >
      {children}
    </div>
  );
}

export function Features() {
  const ref = useReveal<HTMLElement>({ stagger: 0.08 });

  return (
    <section ref={ref} id="features" className="section">
      <div className="shell">
        <div className="grid items-end gap-11 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,.85fr)]">
          <h2 className="reveal h2">What happens in the fifteen minutes before the doctor.</h2>
          <p className="reveal lede">
            The patient works through the kiosk alone or with a helper. Everything it collects is stored with its
            source, its confidence, and the raw original beside it.
          </p>
        </div>

        <div className="mt-16 grid grid-cols-1 gap-[18px] lg:grid-cols-12">
          <article className="reveal cell pb-0 lg:col-span-7">
            <Icon><MessageSquare size={17} /></Icon>
            <h3 className="text-[clamp(1.15rem,1.7vw,1.4rem)] text-ice">An interview that changes shape with the answer</h3>
            <p className="mt-2.5 max-w-[46ch] text-[0.93rem] leading-relaxed text-mute">
              Say chest pain and it asks about onset, site, character, radiation and breathlessness in clinical order.
              Say fever and it takes a different branch entirely. The pathways are structured and reviewable — the model
              phrases the question, it doesn&apos;t invent the question.
            </p>
            <div className="-mx-[clamp(20px,2.4vw,30px)] mt-[22px] border-t border-hair px-[clamp(20px,2.4vw,30px)] pb-6 pt-5">
              <div className="mt-2.5 max-w-[80%] rounded-[14px] rounded-bl-[5px] border border-[rgba(79,216,228,.18)] bg-[rgba(79,216,228,.09)] px-3.5 py-2.5 text-[0.9rem] leading-snug text-[#CFF3F7]">
                ಎದೆನೋವು ಯಾವಾಗ ಶುರುವಾಯಿತು?
                <small className="mt-1.5 block text-[0.72rem] text-dim">When did the chest pain start? — asked aloud and on screen</small>
              </div>
              <div className="ml-auto mt-2.5 max-w-[80%] rounded-[14px] rounded-br-[5px] border border-hair bg-[rgba(143,182,196,.08)] px-3.5 py-2.5 text-[0.9rem] leading-snug text-ice">
                ಇಂದು ಬೆಳಿಗ್ಗೆ, ಸುಮಾರು 6 ಗಂಟೆಗೆ
                <small className="mt-1.5 block text-[0.72rem] text-dim">spoken answer, transcribed</small>
              </div>
              <div className="mt-2.5 max-w-[80%] rounded-[14px] rounded-bl-[5px] border border-[rgba(79,216,228,.18)] bg-[rgba(79,216,228,.09)] px-3.5 py-2.5 text-[0.9rem] leading-snug text-[#CFF3F7]">
                ಉಸಿರಾಟದ ತೊಂದರೆ ಇದೆಯೇ?
                <small className="mt-1.5 block text-[0.72rem] text-dim">Any difficulty breathing? — follow-up chosen by the pathway</small>
              </div>
            </div>
          </article>

          <article className="reveal cell lg:col-span-5">
            <Icon><Mic size={17} /></Icon>
            <h3 className="text-[clamp(1.15rem,1.7vw,1.4rem)] text-ice">Voice first, because reading is not a given</h3>
            <p className="mt-2.5 max-w-[46ch] text-[0.93rem] leading-relaxed text-mute">
              Questions are read aloud and answers can be spoken, in English, Hindi or Kannada. Typing is always
              available as a fallback, and the language can be switched at any point without losing the interview.
            </p>
            <div className="mt-[18px] flex flex-wrap gap-2">
              {['English', 'हिंदी', 'ಕನ್ನಡ', 'Text fallback always on'].map((l, i) => (
                <span
                  key={l}
                  className={`rounded-[9px] border px-3 py-[7px] text-[0.85rem] ${
                    i === 0
                      ? 'border-[rgba(79,216,228,.4)] bg-[rgba(79,216,228,.09)] text-cyan'
                      : 'border-hair bg-[rgba(143,182,196,.05)] text-mute'
                  }`}
                >
                  {l}
                </span>
              ))}
            </div>
            <p className="mt-4 text-[0.875rem] leading-relaxed text-dim">
              Speech, text-to-speech, OCR and the model all sit behind swappable interfaces, so a provider can be
              replaced without touching the clinical logic.
            </p>
          </article>

          <article className="reveal cell lg:col-span-4">
            <Icon tone="flag"><AlertTriangle size={17} /></Icon>
            <h3 className="text-[clamp(1.15rem,1.7vw,1.4rem)] text-ice">Red flags move the queue, not the diagnosis</h3>
            <p className="mt-2.5 text-[0.93rem] leading-relaxed text-mute">
              Rule-based checks watch the structured answers for patterns that need a human sooner — and say exactly
              that. No condition is ever named to the patient.
            </p>
          </article>

          <article className="reveal cell lg:col-span-4">
            <Icon><FileText size={17} /></Icon>
            <h3 className="text-[clamp(1.15rem,1.7vw,1.4rem)] text-ice">It reads the paper they brought</h3>
            <p className="mt-2.5 text-[0.93rem] leading-relaxed text-mute">
              Prescriptions, lab reports and discharge summaries go through OCR and medical entity extraction. The
              original scan stays on screen next to every extracted field.
            </p>
          </article>

          <article className="reveal cell lg:col-span-4">
            <Icon><GitBranch size={17} /></Icon>
            <h3 className="text-[clamp(1.15rem,1.7vw,1.4rem)] text-ice">One timeline out of many visits</h3>
            <p className="mt-2.5 text-[0.93rem] leading-relaxed text-mute">
              Everything with a date — old diagnoses, drugs, investigations, admissions, today&apos;s answers — merges
              into a single chronology the doctor can scan in seconds.
            </p>
          </article>

          <article className="reveal cell lg:col-span-6">
            <Icon><ShieldCheck size={17} /></Icon>
            <h3 className="text-[clamp(1.15rem,1.7vw,1.4rem)] text-ice">Every field says where it came from</h3>
            <p className="mt-2.5 max-w-[46ch] text-[0.93rem] leading-relaxed text-mute">
              Nothing on the doctor&apos;s screen is unattributed. A value is either something the patient said,
              something lifted off a document, something the model inferred, or something the doctor has signed off —
              and it is labelled as such, permanently.
            </p>
            <div className="mt-4 flex flex-wrap gap-[7px]">
              <span className="chip border-[rgba(79,216,228,.32)] text-[#9EE7EF]">Patient-provided</span>
              <span className="chip border-[rgba(59,118,246,.36)] text-[#A9C2FA]">Document-extracted</span>
              <span className="chip border-[rgba(242,169,59,.34)] text-[#F5CE93]">AI-inferred draft</span>
              <span className="chip border-[rgba(120,230,170,.34)] text-[#A6EBC8]">Doctor-verified</span>
            </div>
          </article>

          <article className="reveal cell lg:col-span-6">
            <Icon><Share2 size={17} /></Icon>
            <h3 className="text-[clamp(1.15rem,1.7vw,1.4rem)] text-ice">Built to hand off to ABDM</h3>
            <p className="mt-2.5 max-w-[46ch] text-[0.93rem] leading-relaxed text-mute">
              ABHA linkage, consent artefacts and a FHIR-shaped export sit behind one gateway interface with a mock
              adapter for the demo and an empty real adapter beside it. The demo never pretends to be a live national
              integration.
            </p>
            <p className="mt-3.5 text-[0.875rem] leading-relaxed text-dim">
              Consent is captured before a single question is asked, is explained aloud, and can be withdrawn.
            </p>
          </article>
        </div>
      </div>
    </section>
  );
}
