import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { gauss, view } from '@/lib/view';

/**
 * Two strands orbiting the core: what the patient said (cyan) and what was read
 * off their documents (blue), with rungs where the two merge into one record.
 * Nodes brighten in sequence, so the strands read as data moving, not decoration.
 */
export function DataHelix({ count }: { count: number }) {
  const a = useRef<THREE.InstancedMesh>(null);
  const b = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);

  const { nodesA, nodesB, rungs } = useMemo(() => {
    const nA: THREE.Vector3[] = [];
    const nB: THREE.Vector3[] = [];
    const r: number[] = [];
    for (let i = 0; i < count; i++) {
      const t = count > 1 ? i / (count - 1) : 0;
      const y = (t - 0.5) * 5.0;
      const ang = t * Math.PI * 3.4;
      const rad = 2.05 + Math.sin(t * Math.PI) * 0.42;
      const pa = new THREE.Vector3(Math.cos(ang) * rad, y, Math.sin(ang) * rad);
      const pb = new THREE.Vector3(Math.cos(ang + Math.PI) * rad, y, Math.sin(ang + Math.PI) * rad);
      nA.push(pa);
      nB.push(pb);
      if (i % 3 === 0) r.push(pa.x, pa.y, pa.z, pb.x, pb.y, pb.z);
    }
    return { nodesA: nA, nodesB: nB, rungs: new Float32Array(r) };
  }, [count]);

  useFrame(({ clock }) => {
    if (!a.current || !b.current) return;
    const t = clock.elapsedTime;
    for (let i = 0; i < count; i++) {
      const p1 = view.reduced ? 0 : gauss((t * 0.34 + i / count) % 1, 0.5, 0.055, 1);
      dummy.position.copy(nodesA[i]);
      dummy.scale.setScalar(1 + p1 * 1.5);
      dummy.updateMatrix();
      a.current.setMatrixAt(i, dummy.matrix);

      const p2 = view.reduced ? 0 : gauss((t * 0.34 + i / count + 0.5) % 1, 0.5, 0.055, 1);
      dummy.position.copy(nodesB[i]);
      dummy.scale.setScalar(1 + p2 * 1.5);
      dummy.updateMatrix();
      b.current.setMatrixAt(i, dummy.matrix);
    }
    a.current.instanceMatrix.needsUpdate = true;
    b.current.instanceMatrix.needsUpdate = true;
  });

  return (
    <group>
      <instancedMesh ref={a} args={[null!, null!, count]} frustumCulled={false}>
        <sphereGeometry args={[0.055, 8, 8]} />
        <meshBasicMaterial color="#8DF0F8" />
      </instancedMesh>
      <instancedMesh ref={b} args={[null!, null!, count]} frustumCulled={false}>
        <sphereGeometry args={[0.055, 8, 8]} />
        <meshBasicMaterial color="#89AEFC" />
      </instancedMesh>

      {!view.small && (
        <lineSegments>
          <bufferGeometry>
            <bufferAttribute attach="attributes-position" args={[rungs, 3]} />
          </bufferGeometry>
          <lineBasicMaterial color="#4FD8E4" transparent opacity={0.14} />
        </lineSegments>
      )}
    </group>
  );
}
