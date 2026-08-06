import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { MeshDistortMaterial, Sphere } from '@react-three/drei';
import * as THREE from 'three';
import { userPalette } from '../../design/tokens';

const SPIN = {
  idle: 0.05,
  connecting: 0.10,
  listening: 0.15,   // Rotation when user speaks
  thinking: 0.35,    // Spin during processing
  speaking: 0.18,    // Turn while speaking
  error: 0.02,
};

/**
 * Core — Radiant Emerald 3D Wavy Energy Sphere emitting light (for /user portal).
 *
 * Built with MeshDistortMaterial for 100% reliable WebGL rendering, zero shader crashes,
 * rich 3D specular depth, and full voice reactivity (STT user mic + TTS bot audio).
 */
export function Core({
  status = 'idle',
  audioLevel = 0,   // TTS playback amplitude (0-1) -> Bot speaking
  listenLevel = 0,  // STT mic input amplitude (0-1) -> User speaking
  palette = userPalette,
  radius = 1.30,
}) {
  const meshRef = useRef(null);
  const matRef = useRef(null);
  const glowRef = useRef(null);

  const colors = useMemo(() => ({
    dim: new THREE.Color(palette.dim || 'hsl(165, 85%, 22%)'),
    mid: new THREE.Color(palette.mid || 'hsl(160, 90%, 42%)'),
    bright: new THREE.Color(palette.bright || 'hsl(155, 95%, 58%)'),
    bloom: new THREE.Color(palette.bloom || 'hsl(150, 100%, 82%)'),
  }), [palette]);

  useFrame((state, delta) => {
    if (!meshRef.current || !matRef.current) return;

    // Combined voice energy (STT user mic input + TTS bot playback)
    const voiceEnergy = Math.max(listenLevel, audioLevel);

    // Gentle 3D rotation
    meshRef.current.rotation.y += delta * (SPIN[status] || 0.05);
    meshRef.current.rotation.x = Math.sin(meshRef.current.rotation.y * 0.5) * 0.04;

    // Organic wavy fluid distortion: calm fluid breath when idle, energetic ripples on voice
    const baseDistort = status === 'listening' ? 0.45 : status === 'speaking' ? 0.50 : status === 'thinking' ? 0.65 : 0.32;
    const targetDistort = baseDistort + voiceEnergy * 0.40;
    matRef.current.distort = THREE.MathUtils.lerp(matRef.current.distort, targetDistort, 0.12);

    const baseSpeed = status === 'thinking' ? 3.5 : status === 'speaking' ? 2.8 : 1.2;
    matRef.current.speed = THREE.MathUtils.lerp(matRef.current.speed, baseSpeed + voiceEnergy * 3.0, 0.10);

    // Dynamic 3D Scale pulse on voice amplitude
    const baseScale = radius;
    const targetScale = baseScale * (1 + voiceEnergy * 0.28 + (status === 'thinking' ? 0.08 : 0));
    meshRef.current.scale.setScalar(THREE.MathUtils.lerp(meshRef.current.scale.x, targetScale, 0.15));

    // Outer glow halo pulse
    if (glowRef.current) {
      glowRef.current.scale.setScalar(meshRef.current.scale.x * 1.35);
      glowRef.current.material.opacity = THREE.MathUtils.lerp(
        glowRef.current.material.opacity,
        0.12 + voiceEnergy * 0.25 + (status === 'speaking' ? 0.10 : 0),
        0.12
      );
    }

    // Color transition based on status & audio amplitude
    let targetColor = colors.dim;
    let targetEmissive = colors.mid;
    let targetIntensity = 0.6;

    if (status === 'listening') {
      targetColor = colors.mid;
      targetEmissive = colors.bright;
      targetIntensity = 0.8 + listenLevel * 0.6;
    } else if (status === 'thinking') {
      targetColor = colors.bright;
      targetEmissive = colors.bloom;
      targetIntensity = 1.2;
    } else if (status === 'speaking') {
      targetColor = colors.mid;
      targetEmissive = colors.bright;
      targetIntensity = 0.9 + audioLevel * 0.8;
    } else if (status === 'connecting') {
      targetColor = colors.dim;
      targetEmissive = colors.mid;
      targetIntensity = 0.5;
    }

    matRef.current.color.lerp(targetColor, 0.08);
    matRef.current.emissive.lerp(targetEmissive, 0.08);
    matRef.current.emissiveIntensity = THREE.MathUtils.lerp(
      matRef.current.emissiveIntensity,
      targetIntensity,
      0.08
    );
  });

  return (
    <group>
      {/* Outer Ethereal Atmosphere Glow */}
      <Sphere ref={glowRef} args={[1, 32, 32]}>
        <meshBasicMaterial
          color="hsl(155, 95%, 58%)"
          transparent
          opacity={0.12}
          side={THREE.BackSide}
        />
      </Sphere>

      {/* Main Wavy Fluid Energy Sphere */}
      <Sphere ref={meshRef} args={[1, 64, 64]}>
        <MeshDistortMaterial
          ref={matRef}
          color="hsl(165, 85%, 22%)"
          emissive="hsl(160, 90%, 42%)"
          emissiveIntensity={0.6}
          roughness={0.2}
          metalness={0.8}
          distort={0.32}
          speed={1.2}
        />
      </Sphere>

      {/* Inner Dynamic Point Light for rich 3D volumetric specular highlights */}
      <pointLight color="hsl(155, 95%, 58%)" intensity={1.5 + (listenLevel + audioLevel) * 2} distance={6} />
      <pointLight color="hsl(160, 90%, 42%)" intensity={0.8} distance={8} position={[0, -1, 0]} />
    </group>
  );
}
