import { useEffect, useState } from 'react';
import { Logo } from './Logo';

const LINKS = [
  { href: '#top', label: 'Home' },
  { href: '#features', label: 'Features' },
  { href: '#how', label: 'How it works' },
  { href: '#doctors', label: 'Doctors' },
  { href: '#about', label: 'About' },
];

export function Navbar() {
  const [stuck, setStuck] = useState(false);

  useEffect(() => {
    const onScroll = () => setStuck(window.scrollY > 24);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header
      className={[
        'fixed left-1/2 top-3.5 z-[60] flex w-[min(calc(100%-24px),1280px)] -translate-x-1/2 items-center gap-2',
        'rounded-2xl border py-2.5 pl-[18px] pr-2.5 transition-all duration-300',
        stuck
          ? 'border-hair bg-[rgba(7,12,19,.62)] shadow-[0_18px_50px_-30px_rgba(0,0,0,.95)] backdrop-blur-xl backdrop-saturate-150'
          : 'border-transparent bg-transparent',
      ].join(' ')}
    >
      <a href="#top" className="flex flex-none items-center gap-2.5 font-display text-[1.06rem] font-semibold tracking-[-0.03em] text-ice no-underline">
        <Logo />
        MediKiosk
      </a>

      <nav aria-label="Primary" className="ml-4 hidden items-center gap-1 lg:flex">
        {LINKS.map((l) => (
          <a
            key={l.href}
            href={l.href}
            className="rounded-[9px] px-3 py-2 text-[0.9rem] text-mute no-underline transition-colors hover:bg-[rgba(143,182,196,.08)] hover:text-ice"
          >
            {l.label}
          </a>
        ))}
      </nav>

      <div className="flex-1" />

      <div className="flex flex-none items-center gap-2">
        <a href="#login" className="btn btn-ghost hidden sm:inline-flex">
          Log in
        </a>
        <a href="#start" className="btn btn-primary">
          Get started
        </a>
      </div>
    </header>
  );
}
