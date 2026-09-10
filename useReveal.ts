import { useEffect, useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

/**
 * Staggered entrance for the direct `.reveal` descendants of a section.
 * One orchestrated reveal per section, not a separate animation per element.
 */
export function useReveal<T extends HTMLElement>(opts?: { stagger?: number; y?: number }) {
  const ref = useRef<T>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const targets = el.querySelectorAll<HTMLElement>('.reveal');
    if (!targets.length) return;

    const ctx = gsap.context(() => {
      gsap.fromTo(
        targets,
        { opacity: 0, y: opts?.y ?? 18 },
        {
          opacity: 1,
          y: 0,
          duration: 0.85,
          ease: 'power3.out',
          stagger: opts?.stagger ?? 0.09,
          scrollTrigger: { trigger: el, start: 'top 82%', once: true },
        },
      );
    }, el);

    return () => ctx.revert();
  }, [opts?.stagger, opts?.y]);

  return ref;
}
