import { useFrame } from '@react-three/fiber';
import { useRef } from 'react';
import { damp, view } from '@/lib/view';

/** Camera positions matched to the seven scroll keyframes in VitalCore. */
const SHOTS = [
  { p: 0.0, cam: [0.0, 0.15, 8.6] },
  { p: 0.15, cam: [0.5, 0.55, 7.4] },
  { p: 0.33, cam: [-0.35, 0.1, 6.5] },
  { p: 0.52, cam: [0.0, -0.25, 5.0] },
  { p: 0.71, cam: [0.45, 0.35, 7.0] },
  { p: 0.87, cam: [0.0, 0.05, 7.8] },
  { p: 1.0, cam: [0.0, 0.0, 11.6] },
] as const;

const smooth = (x: number) => x * x * (3 - 2 * x);

export function CameraRig() {
  const mx = useRef(0);
  const my = useRef(0);

  useFrame(({ camera }, delta) => {
    const dt = Math.min(0.05, delta);
    const p = view.progress;

    let i = 0;
    for (; i < SHOTS.length - 2; i++) if (p < SHOTS[i + 1].p) break;
    const a = SHOTS[i];
    const b = SHOTS[i + 1];
    const span = b.p - a.p;
    const t = smooth(span > 0 ? Math.min(1, Math.max(0, (p - a.p) / span)) : 0);

    mx.current += (view.mx - mx.current) * damp(dt, 2.6);
    my.current += (view.my - my.current) * damp(dt, 2.6);
    const par = view.reduced ? 0 : 1;

    const tx = a.cam[0] + (b.cam[0] - a.cam[0]) * t + mx.current * 0.55 * par;
    const ty = a.cam[1] + (b.cam[1] - a.cam[1]) * t - my.current * 0.34 * par;
    const tz = a.cam[2] + (b.cam[2] - a.cam[2]) * t;

    camera.position.x += (tx - camera.position.x) * damp(dt, 2.2);
    camera.position.y += (ty - camera.position.y) * damp(dt, 2.2);
    camera.position.z += (tz - camera.position.z) * damp(dt, 2.2);
    camera.lookAt(0, 0, 0);
  });

  return null;
}
