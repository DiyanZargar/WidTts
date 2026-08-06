import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

/**
 * ParticleVoid — Dense, rich cosmic stardust background field (Radiant Emerald Palette).
 *
 * Positioned cleanly behind the camera (Z depth -4 to -22) so particles are richly dense
 * at idle, but NEVER fly into the camera lens or scatter aggressively during scroll.
 */

function ParticleLayer({ count, sizeRange, spreadRadius, spreadY, speed, opacity, palette }) {
  const pointsRef = useRef();

  const [positions, colors] = useMemo(() => {
    const pos = new Float32Array(count * 3);
    const col = new Float32Array(count * 3);

    for (let i = 0; i < count; i++) {
      const theta = i * 2.3998277; // Golden angle
      const r = 2.0 + Math.sqrt(i / count) * spreadRadius; // Radial offset away from camera center
      const yOffset = -(Math.random() * spreadY) + spreadY * 0.1;

      pos[i * 3] = Math.cos(theta) * r;
      pos[i * 3 + 1] = yOffset;
      // Push particles back into Z-depth (-4 to -24) so camera scroll never collides with lens
      pos[i * 3 + 2] = -4 - Math.abs(Math.sin(theta)) * (r * 0.5);

      const c = palette[Math.floor(Math.random() * palette.length)];
      col[i * 3] = c.r;
      col[i * 3 + 1] = c.g;
      col[i * 3 + 2] = c.b;
    }

    return [pos, col];
  }, [count, spreadRadius, spreadY, palette]);

  useFrame((state) => {
    if (!pointsRef.current) return;
    const t = state.clock.getElapsedTime();
    pointsRef.current.rotation.y = t * speed;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
        <bufferAttribute
          attach="attributes-color"
          args={[colors, 3]}
        />
      </bufferGeometry>
      <pointsMaterial
        size={sizeRange[1]}
        vertexColors
        transparent
        opacity={opacity}
        sizeAttenuation
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

export function UserParticleVoid() {
  const palette = useMemo(() => ({
    dust: [
      new THREE.Color('hsl(165, 60%, 25%)'),
      new THREE.Color('hsl(160, 65%, 32%)'),
      new THREE.Color('hsl(170, 55%, 20%)'),
    ],
    stars: [
      new THREE.Color('hsl(160, 85%, 48%)'),
      new THREE.Color('hsl(155, 95%, 58%)'),
      new THREE.Color('hsl(165, 80%, 42%)'),
    ],
    orbs: [
      new THREE.Color('hsl(155, 95%, 68%)'),
      new THREE.Color('hsl(150, 100%, 78%)'),
    ],
  }), []);

  return (
    <group>
      <ParticleLayer
        count={450}
        sizeRange={[0.01, 0.035]}
        spreadRadius={28}
        spreadY={90}
        speed={0.002}
        opacity={0.45}
        palette={palette.dust}
      />
      <ParticleLayer
        count={150}
        sizeRange={[0.04, 0.08]}
        spreadRadius={24}
        spreadY={90}
        speed={0.004}
        opacity={0.65}
        palette={palette.stars}
      />
      <ParticleLayer
        count={35}
        sizeRange={[0.10, 0.20]}
        spreadRadius={20}
        spreadY={90}
        speed={0.007}
        opacity={0.55}
        palette={palette.orbs}
      />
    </group>
  );
}

export function ParticleVoid() {
  const palette = useMemo(() => ({
    dust: [
      new THREE.Color('hsl(165, 60%, 25%)'),
      new THREE.Color('hsl(160, 65%, 32%)'),
      new THREE.Color('hsl(170, 55%, 20%)'),
    ],
    stars: [
      new THREE.Color('hsl(160, 85%, 48%)'),
      new THREE.Color('hsl(155, 95%, 58%)'),
      new THREE.Color('hsl(165, 80%, 42%)'),
    ],
    orbs: [
      new THREE.Color('hsl(155, 95%, 68%)'),
      new THREE.Color('hsl(150, 100%, 78%)'),
    ],
  }), []);

  return (
    <group>
      {/* Layer 1: Dust — dense background haze */}
      <ParticleLayer
        count={500}
        sizeRange={[0.01, 0.035]}
        spreadRadius={30}
        spreadY={120}
        speed={0.002}
        opacity={0.45}
        palette={palette.dust}
      />

      {/* Layer 2: Stars — vibrant midground stars */}
      <ParticleLayer
        count={160}
        sizeRange={[0.04, 0.08]}
        spreadRadius={26}
        spreadY={120}
        speed={0.004}
        opacity={0.65}
        palette={palette.stars}
      />

      {/* Layer 3: Orbs — rich glowing accents */}
      <ParticleLayer
        count={40}
        sizeRange={[0.10, 0.20]}
        spreadRadius={22}
        spreadY={120}
        speed={0.007}
        opacity={0.55}
        palette={palette.orbs}
      />
    </group>
  );
}
