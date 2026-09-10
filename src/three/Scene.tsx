import { Canvas } from '@react-three/fiber';
import { AdaptiveDpr, AdaptiveEvents, Preload } from '@react-three/drei';
import * as THREE from 'three';
import { useEffect, useRef } from 'react';
import { view } from '@/lib/view';
import { VitalCore } from './VitalCore';
import { CameraRig } from './CameraRig';
import { Particles } from './Particles';

/** Keeps the page readable where text sits over the scene. */
function Scrim() {
  const el = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let raf = 0;
    let last = -1;
    const tick = () => {
      if (el.current && view.dim !== last) {
        el.current.style.opacity = view.dim.toFixed(3);
        last = view.dim;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);
  return (
    <div
      ref={el}
      aria-hidden
      className="pointer-events-none fixed inset-0 z-[1] bg-void opacity-0 transition-opacity duration-500"
    />
  );
}

export default function Scene() {
  const small = view.small;

  return (
    <>
      <div className="pointer-events-none fixed inset-0 z-0">
        <Canvas
          aria-hidden
          dpr={[1, small ? 1.5 : 2]}
          gl={{ antialias: !small, alpha: true, powerPreference: 'high-performance' }}
          camera={{ fov: 42, position: [0, 0.15, 8.6], near: 0.1, far: 90 }}
          onCreated={({ gl, scene }) => {
            gl.toneMapping = THREE.ACESFilmicToneMapping;
            gl.toneMappingExposure = 1.15;
            scene.fog = new THREE.FogExp2('#04070C', 0.055);
          }}
        >
          <ambientLight color="#0E2431" intensity={1.15} />
          <pointLight color="#4FD8E4" intensity={2.7} distance={26} decay={2} position={[3.6, 3, 3.6]} />
          <pointLight color="#3B76F6" intensity={2.2} distance={28} decay={2} position={[-4.6, -2.4, 2.6]} />
          <directionalLight color="#DFF6FF" intensity={0.45} position={[-2, 4, -5]} />

          <VitalCore />
          <Particles count={small ? 340 : 1300} />

          <CameraRig />
          <AdaptiveDpr pixelated />
          <AdaptiveEvents />
          <Preload all />
        </Canvas>
      </div>
      <Scrim />
    </>
  );
}
