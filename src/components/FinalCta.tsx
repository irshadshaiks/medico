import { ArrowRight } from 'lucide-react';
import { useReveal } from '@/hooks/useReveal';

export function FinalCta() {
  const ref = useReveal<HTMLElement>();
  return (
    <section ref={ref} id="start" className="py-[clamp(100px,13vw,180px)] text-center">
      <div className="shell">
        <h2 className="reveal mx-auto max-w-[19ch] text-[clamp(2.1rem,4.6vw,3.7rem)]">
          Give the consultation its history back.
        </h2>
        <p className="reveal lede mx-auto mt-[22px] text-center">
          Run the full patient journey, then switch to the doctor view and verify the case yourself.
        </p>
        <div className="reveal mt-[34px] flex flex-wrap justify-center gap-3">
          <a href="#start" className="btn btn-primary btn-lg group">
            Start a patient intake
            <ArrowRight size={16} className="transition-transform duration-200 group-hover:translate-x-0.5" />
          </a>
          <a href="#login" id="login" className="btn btn-lg">
            Log in
          </a>
        </div>
      </div>
    </section>
  );
}
