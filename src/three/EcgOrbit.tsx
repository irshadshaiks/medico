import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { ecg, view } from '@/lib/view';
import { glowTexture } from './glow';

/** A cardiac trace bent into a ring, with a pulse travelling along it. */
export function EcgOrbit({ segments }: { segments: number }) {
  const pulse = useRef<THREE.Group>(null);
  const sprite = useRef<THREE.Sprite>(null);
  const tex = useMemo(() => glowTexture(), []);

  const curve = useMemo(() => {
    const pts: THREE.Vector3[] = [];
    const M = segments;
    for (let j = 0; j < M; j++) {
      const u = j / M;
      const ang = u * Math.PI * 2;
      pts.push(new THREE.Vector3(Math.cos(ang) * 2.95, ecg(u * 3) * 0.62, Math.sin(ang) * 2.95));
    }
    return new THREE.CatmullRomCurve3(pts, true, 'catmullrom', 0.25);
  }, [segments]);

  useFrame(({ clock }) => {
    if (!pulse.current) return;
    const u = view.reduced ? 0 : (clock.elapsedTime * 0.11) % 1;
    const p = curve.getPointAt(u);
    pulse.current.position.copy(p);
    if (sprite.current) {
      const beat = view.reduced ? 0 : Math.max(0, Math.sin(clock.elapsedTime * 6.4));
      (sprite.current.material as THREE.SpriteMaterial).opacity = 0.55 + beat * 0.3;
    }
  });

  return (
    <group rotation={[0.44, 0, -0.16]}>
      <mesh>
        <tubeGeometry args={[curve, segments * 1.6, 0.019, 6, true]} />
        <meshBasicMaterial color="#4FD8E4" transparent opacity={0.42} />
      </mesh>
      <group ref={pulse}>
        <mesh>
          <sphereGeometry args={[0.05, 8, 8]} />
          <meshBasicMaterial color="#D8FBFF" />
        </mesh>
        <sprite ref={sprite} scale={[1.1, 1.1, 1]}>
          <spriteMaterial
            map={tex}
            color="#9BEEFA"
            transparent
            opacity={0.85}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </sprite>
      </group>
    </group>
  );
}
