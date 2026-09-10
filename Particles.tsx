import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { view } from '@/lib/view';
import { glowTexture } from './glow';

export function Particles({ count }: { count: number }) {
  const ref = useRef<THREE.Points>(null);
  const tex = useMemo(() => glowTexture(), []);

  const positions = useMemo(() => {
    const p = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const r = 4 + Math.pow(Math.random(), 0.6) * 10;
      const th = Math.random() * Math.PI * 2;
      const ph = Math.acos(2 * Math.random() - 1);
      p[i * 3] = r * Math.sin(ph) * Math.cos(th);
      p[i * 3 + 1] = r * Math.cos(ph) * 0.62;
      p[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th);
    }
    return p;
  }, [count]);

  useFrame(({ clock }) => {
    if (!ref.current || view.reduced) return;
    ref.current.rotation.y = -clock.elapsedTime * 0.045;
    ref.current.rotation.x = Math.sin(clock.elapsedTime * 0.08) * 0.06;
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        map={tex}
        color="#8FD6E6"
        size={view.small ? 0.075 : 0.09}
        sizeAttenuation
        transparent
        opacity={0.5}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  );
}
