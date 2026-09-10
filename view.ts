/**
 * A tiny mutable store read inside useFrame.
 *
 * Scroll position and pointer position change on every frame; putting them in
 * React state would re-render the whole tree 60 times a second. Nothing here is
 * reactive on purpose — the 3D scene reads it directly.
 */
export const view = {
  progress: 0, // 0 at the top of the document, 1 at the bottom
  mx: 0, // pointer x, -1 to 1
  my: 0, // pointer y, -1 to 1
  small: false, // phone / coarse pointer
  reduced: false, // prefers-reduced-motion
  dim: 0, // legibility scrim opacity, written by the camera rig
};

export function readEnvironment() {
  view.small =
    window.innerWidth < 820 ||
    (window.matchMedia('(pointer:coarse)').matches && window.innerWidth < 1100);
  view.reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export function gauss(x: number, mu: number, s: number, a: number) {
  const d = x - mu;
  return a * Math.exp(-(d * d) / (2 * s * s));
}

/** One cardiac cycle, used for both the ECG orbit geometry and the core's beat. */
export function ecg(x: number) {
  const t = x - Math.floor(x);
  return (
    gauss(t, 0.16, 0.03, 0.2) +
    gauss(t, 0.3, 0.012, -0.22) +
    gauss(t, 0.35, 0.012, 1.0) +
    gauss(t, 0.4, 0.014, -0.34) +
    gauss(t, 0.6, 0.055, 0.32)
  );
}

export const damp = (dt: number, speed: number) => Math.min(1, dt * speed);
