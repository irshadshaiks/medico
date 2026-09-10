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

import { LoginModal } from '@/components/LoginModal';
import { PatientIntake } from '@/components/PatientIntake';
import { DoctorDashboard } from '@/components/DoctorDashboard';
import { DoctorCaseFile } from '@/components/DoctorCaseFile';

// three, r3f and drei are a large bundle — keep them out of first paint.
const Scene = lazy(() => import('@/three/Scene'));

export default function App() {
  useViewSync();
  const [scene, setScene] = useState(false);

  // App routing state
  const [currentView, setCurrentView] = useState<'landing' | 'kiosk' | 'doctor-queue' | 'case-file'>('landing');
  const [activeCaseId, setActiveCaseId] = useState<string>('case-rk-001');
  const [isLoginOpen, setIsLoginOpen] = useState(false);

  useEffect(() => {
    // Let the text render and settle before the WebGL context spins up.
    const start = () => setScene(true);
    const win = window as any;
    const id = win.requestIdleCallback ? win.requestIdleCallback(start) : setTimeout(start, 400);
    return () => {
      if (win.cancelIdleCallback) {
        win.cancelIdleCallback(id);
      } else {
        clearTimeout(id);
      }
    };
  }, []);

  // Hash change routing
  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.toLowerCase();
      if (hash === '#login') {
        setIsLoginOpen(true);
      } else if (hash === '#start' || hash === '#kiosk') {
        setCurrentView('kiosk');
        setIsLoginOpen(false);
      } else if (hash === '#doctor-queue' || hash === '#doctor-dashboard' || hash === '#doctor') {
        setCurrentView('doctor-queue');
        setIsLoginOpen(false);
      } else if (hash.startsWith('#case/')) {
        const cId = window.location.hash.replace('#case/', '');
        if (cId) setActiveCaseId(cId);
        setCurrentView('case-file');
        setIsLoginOpen(false);
      } else if (hash === '#top' || hash === '' || hash === '#main') {
        setCurrentView('landing');
        setIsLoginOpen(false);
      }
    };

    handleHashChange();
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const handleLoginSuccess = (role: string) => {
    if (role === 'doctor') {
      window.location.hash = '#doctor-queue';
      setCurrentView('doctor-queue');
    } else {
      window.location.hash = '#kiosk';
      setCurrentView('kiosk');
    }
  };

  const handleBackToLanding = () => {
    window.location.hash = '#top';
    setCurrentView('landing');
  };

  return (
    <>
      <a
        href="#main"
        className="btn absolute left-[-9999px] top-2 z-[99] focus:left-3"
      >
        Skip to content
      </a>

      {scene && !view.reduced && currentView === 'landing' && (
        <Suspense fallback={null}>
          <Scene />
        </Suspense>
      )}

      {/* Persistent Navbar */}
      <Navbar />

      {/* Main View Switcher */}
      {currentView === 'landing' && (
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
      )}

      {currentView === 'kiosk' && (
        <main className="relative z-[2]">
          <PatientIntake
            onComplete={(caseId) => {
              setActiveCaseId(caseId);
              window.location.hash = '#doctor-queue';
              setCurrentView('doctor-queue');
            }}
            onBackHome={handleBackToLanding}
          />
        </main>
      )}

      {currentView === 'doctor-queue' && (
        <main className="relative z-[2]">
          <DoctorDashboard
            onSelectCase={(caseId) => {
              setActiveCaseId(caseId);
              window.location.hash = `#case/${caseId}`;
              setCurrentView('case-file');
            }}
            onBackHome={handleBackToLanding}
            onNewIntake={() => {
              window.location.hash = '#kiosk';
              setCurrentView('kiosk');
            }}
          />
        </main>
      )}

      {currentView === 'case-file' && (
        <main className="relative z-[2]">
          <DoctorCaseFile
            caseId={activeCaseId}
            onBackToQueue={() => {
              window.location.hash = '#doctor-queue';
              setCurrentView('doctor-queue');
            }}
          />
        </main>
      )}

      {/* Login Modal */}
      <LoginModal
        isOpen={isLoginOpen}
        onClose={() => {
          setIsLoginOpen(false);
          if (window.location.hash === '#login') {
            window.location.hash = '#top';
          }
        }}
        onSuccess={handleLoginSuccess}
      />
    </>
  );
}
