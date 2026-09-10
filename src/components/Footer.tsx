import { Logo } from './Logo';

const LINKS = [
  { href: '#features', label: 'Features' },
  { href: '#how', label: 'How it works' },
  { href: '#doctors', label: 'Doctors' },
  { href: '#safety', label: 'Safety model' },
  { href: '#about', label: 'About' },
];

export function Footer() {
  return (
    <footer className="border-t border-hair bg-[rgba(4,7,12,.7)] pb-[46px] pt-[38px]">
      <div className="shell flex flex-wrap items-start justify-between gap-7">
        <div>
          <a href="#top" className="mb-2.5 flex items-center gap-2.5 font-display text-[1.06rem] font-semibold tracking-[-0.03em] text-ice no-underline">
            <Logo size={22} />
            MediKiosk
          </a>
          <p className="max-w-[34ch] text-[0.875rem] leading-relaxed text-dim">
            A pre-consultation case-taking system. Demonstration build using synthetic patients only — no real patient
            data is present anywhere in this software.
          </p>
        </div>
        <nav aria-label="Footer" className="flex flex-wrap gap-6">
          {LINKS.map((l) => (
            <a key={l.href} href={l.href} className="text-[0.86rem] text-dim no-underline hover:text-ice">
              {l.label}
            </a>
          ))}
        </nav>
      </div>
    </footer>
  );
}
