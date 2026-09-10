import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { damp, gauss, view } from '@/lib/view';
import { glowTexture } from './glow';
import { DataHelix } from './DataHelix';
import { EcgOrbit } from './EcgOrbit';

/** Where the core sits, how big it is, and how dark the page scrim goes, per scroll position. */
const KEYFRAMES = [
  { p: 0.0, pos: [2.55, 0.0, 0.0], scale: 1.0, dim: 0.0 },
  { p: 0.15, pos: [2.1, -0.35, -0.7], scale: 0.94, dim: 0.3 },
  { p: 0.33, pos: [-2.95, 0.15, -0.9], scale: 0.9, dim: 0.44 },
  { p: 0.52, pos: [0.1, 0.2, -2.4], scale: 1.06, dim: 0.56 },
  { p: 0.71, pos: [3.05, -0.1, -1.0], scale: 0.96, dim: 0.38 },
  { p: 0.87, pos: [-2.65, 0.0, -1.5], scale: 0.92, dim: 0.42 },
  { p: 1.0, pos: [0.0, 0.0, 0.0], scale: 1.18, dim: 0.08 },
] as const;

const smooth = (x: number) => x * x * (3 - 2 * x);

function sample(p: number) {
  let i = 0;
  for (; i < KEYFRAMES.length - 2; i++) if (p < KEYFRAMES[i + 1].p) break;
  const a = KEYFRAMES[i];
  const b = KEYFRAMES[i + 1];
  const span = b.p - a.p;
  const t = smooth(span > 0 ? Math.min(1, Math.max(0, (p - a.p) / span)) : 0);
  return {
    x: a.pos[0] + (b.pos[0] - a.pos[0]) * t,
    y: a.pos[1] + (b.pos[1] - a.pos[1]) * t,
    z: a.pos[2] + (b.pos[2] - a.pos[2]) * t,
    s: a.scale + (b.scale - a.scale) * t,
    dim: a.dim + (b.dim - a.dim) * t,
  };
}

/**
 * The unified patient record: a faceted core that beats at about 62bpm, wrapped
 * by the two data strands and orbited by its own cardiac trace.
 */
export function VitalCore() {
  const group = useRef<THREE.Group>(null);
  const inner = useRef<THREE.Mesh>(null);
  const halo = useRef<THREE.Sprite>(null);
  const tex = useMemo(() => glowTexture(), []);
  const spin = useRef(0);

  useFrame((state, delta) => {
    const g = group.current;
    if (!g) return;
    const dt = Math.min(0.05, delta);
    const t = state.clock.elapsedTime;
    const k = sample(view.progress);
    view.dim = k.dim;

    g.position.x += (k.x - g.position.x) * damp(dt, 2.4);
    g.position.y += (k.y - g.position.y) * damp(dt, 2.4);
    g.position.z += (k.z - g.position.z) * damp(dt, 2.4);
    const s = g.scale.x + (k.s - g.scale.x) * damp(dt, 2.4);
    g.scale.setScalar(s);

    if (!view.reduced) {
      spin.current += dt * 0.16;
      g.rotation.y = spin.current + view.progress * 1.5 + view.mx * 0.22;
      g.rotation.x = -view.my * 0.12 + Math.sin(t * 0.25) * 0.03;
    }

    // lub-dub, then a slow relax
    const period = 0.97;
    const bt = (t % period) / period;
    const beat = view.reduced ? 0 : gauss(bt, 0.06, 0.03, 1) + gauss(bt, 0.24, 0.045, 0.5);

    if (inner.current) {
      inner.current.scale.setScalar(1 + beat * 0.05);
      (inner.current.material as THREE.MeshStandardMaterial).emissiveIntensity = 0.6 + beat * 1.1;
    }
    if (halo.current) {
      (halo.current.material as THREE.SpriteMaterial).opacity = 0.32 + beat * 0.3;
      halo.current.scale.setScalar(7.5 + beat * 0.8);
    }
  });

  return (
    <group ref={group} position={[2.55, 0, 0]}>
      <mesh ref={inner}>
        <icosahedronGeometry args={[1.0, 2]} />
        <meshStandardMaterial
          color="#07161F"
          roughness={0.24}
          metalness={0.86}
          emissive="#0A4F5E"
          emissiveIntensity={0.7}
          flatShading
        />
      </mesh>

      <mesh>
        <icosahedronGeometry args={[1.46, 1]} />
        <meshBasicMaterial color="#4FD8E4" wireframe transparent opacity={0.17} />
      </mesh>

      <mesh>
        <icosahedronGeometry args={[1.78, 0]} />
        <meshBasicMaterial
          color="#3B76F6"
          transparent
          opacity={0.055}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      <sprite ref={halo} scale={[7.5, 7.5, 1]}>
        <spriteMaterial
          map={tex}
          color="#4FD8E4"
          transparent
          opacity={0.4}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </sprite>

      <DataHelix count={view.small ? 26 : 44} />
      <EcgOrbit segments={view.small ? 120 : 210} />
    </group>
  );
}
