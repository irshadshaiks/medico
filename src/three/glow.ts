import * as THREE from 'three';

let cached: THREE.CanvasTexture | null = null;

/** A soft radial sprite, generated once. Cheaper and sharper than shipping a PNG. */
export function glowTexture() {
  if (cached) return cached;
  const c = document.createElement('canvas');
  c.width = c.height = 64;
  const g = c.getContext('2d')!;
  const grd = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grd.addColorStop(0, 'rgba(255,255,255,1)');
  grd.addColorStop(0.25, 'rgba(190,245,255,0.75)');
  grd.addColorStop(0.6, 'rgba(120,200,230,0.18)');
  grd.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = grd;
  g.fillRect(0, 0, 64, 64);
  cached = new THREE.CanvasTexture(c);
  return cached;
}
