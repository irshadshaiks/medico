import { useEffect } from 'react';
import { readEnvironment, view } from '@/lib/view';

/**
 * Wires scroll, pointer and media queries into the mutable `view` store.
 * Mounted once, at the top of the app. Causes no re-renders.
 */
export function useViewSync() {
  useEffect(() => {
    readEnvironment();

    let ticking = false;
    const measure = () => {
      const h = document.documentElement.scrollHeight - window.innerHeight;
      view.progress = h > 0 ? Math.min(1, Math.max(0, window.scrollY / h)) : 0;
      ticking = false;
    };
    const onScroll = () => {
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(measure);
      }
    };
    const onPointer = (e: PointerEvent) => {
      view.mx = (e.clientX / window.innerWidth) * 2 - 1;
      view.my = (e.clientY / window.innerHeight) * 2 - 1;
    };
    const onResize = () => {
      readEnvironment();
      measure();
    };

    measure();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('pointermove', onPointer, { passive: true });
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('pointermove', onPointer);
      window.removeEventListener('resize', onResize);
    };
  }, []);
}
