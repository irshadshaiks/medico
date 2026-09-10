import { Suspense, lazy, useEffect, useState } from 'react';
import { useViewSync } from '@/hooks/useViewSync';
import { view } from '@/lib/view';
import { Navbar } from '@/components/Navbar';
import { Hero } from '@/components/Hero';
import { StatStrip } from '@/components/StatStrip';
import { Problem } from '@/components/Problem';
import { Features } from '@/components/Features';
import { HowItWorks } from '@/components/HowItWorks';
import { DoctorView } from '@/components/DoctorView';
import { SafetyBand } from '@/components/SafetyBand';
import { About } from '@/components/About';
import { FinalCta } from '@/components/FinalCta';
import { Footer } from '@/components/Footer';

// three, r3f and drei are a large bundle — keep them out of first paint.
const Scene = lazy(() => import('@/three/Scene'));

export default function App() {
  useViewSync();
  const [scene, setScene] = useState(false);

  useEffect(() => {
    // Let the text render and settle before the WebGL context spins up.
    const start = () => setScene(true);
    const id =
      'requestIdleCallback' in window
        ? (window as unknown as { requestIdleCallback: (cb: () => void) => number }).requestIdleCallback(start)
        : window.setTimeout(start, 400);
    return () => {
      if ('cancelIdleCallback' in window) {
        (window as unknown as { cancelIdleCallback: (h: number) => void }).cancelIdleCallback(id);
      } else {
        clearTimeout(id);
      }
    };
  }, []);

  return (
    <>
      <a
        href="#main"
        className="btn absolute left-[-9999px] top-2 z-[99] focus:left-3"
      >
        Skip to content
      </a>

      {scene && !view.reduced && (
        <Suspense fallback={null}>
          <Scene />
        </Suspense>
      )}

      <Navbar />

      <main id="main" className="relative z-[2]">
        <span id="top" />
        <Hero />
        <StatStrip />
        <Problem />
        <Features />
        <HowItWorks />
        <DoctorView />
        <SafetyBand />
        <About />
        <FinalCta />
        <Footer />
      </main>
    </>
  );
}
