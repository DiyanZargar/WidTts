import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { MeshDistortMaterial, Sphere } from '@react-three/drei';
import * as THREE from 'three';

/**
 * CoreSphere — The central reflective sphere for the Admin Journey.
 * Renders the living Silver Halo in dormant/overview state with organic breathing,
 * transitioning smoothly into warm golden amber as journey progress advances.
 */
export function CoreSphere({ progress = 0, activated = false, isActive = false, position = [0, 0, 0], status, audioLevel = 0, listenLevel = 0 }) {
  const coreRef = useRef();
  const glowRef = useRef();
  const matRef = useRef();
  const lightRef = useRef();
  const lightRef2 = useRef();

  // Silver Halo Palette (Inactive / Overview / Dormant state)
  const silverColors = useMemo(() => ({
    base: new THREE.Color('#b5b5bd'),
    dim: new THREE.Color('#484850'),
    mid: new THREE.Color('#787882'),
    bright: new THREE.Color('#dcdce4'),
    glow: new THREE.Color('#b0b0be'),
  }), []);

  // Warm Golden Amber Palette (Active / In-journey / Live state)
  const amberColors = useMemo(() => ({
    base: new THREE.Color('#dcaa5c'),
    dim: new THREE.Color('#6e4c1e'),
    mid: new THREE.Color('#f0d190'),
    bright: new THREE.Color('#fff3d6'),
    glow: new THREE.Color('#e8c77a'),
  }), []);

  useFrame((state, delta) => {
    if (!coreRef.current || !matRef.current) return;
    const t = state.clock.getElapsedTime();

    // Gentle organic breathing rotation
    coreRef.current.rotation.y += delta * 0.12;
    coreRef.current.rotation.x = Math.sin(t * 0.12) * 0.08;

    // Combined voice amplitude
    const voiceEnergy = Math.max(audioLevel, listenLevel);

    // Calculate progression blend: 0 = pure silver halo, 1 = warm golden amber
    const activeWeight = Math.min(1, Math.max(0, progress * 1.5 + (activated ? 1 : 0) + (isActive ? 1 : 0)));

    // Interpolate base and emissive colors between Silver Halo and Golden Amber
    const baseColor = silverColors.base.clone().lerp(amberColors.base, activeWeight);
    let emissiveColor = silverColors.dim.clone().lerp(amberColors.dim, activeWeight);
    let emissiveIntensity = THREE.MathUtils.lerp(0.35, 0.75, activeWeight);

    if (status === 'speaking') {
      emissiveColor.lerp(amberColors.bright, 0.5 + audioLevel * 0.5);
      emissiveIntensity = 0.8 + audioLevel * 0.9;
    } else if (status === 'listening') {
      emissiveColor.lerp(amberColors.mid, 0.4 + listenLevel * 0.4);
      emissiveIntensity = 0.65 + listenLevel * 0.7;
    } else if (activated) {
      const flarePhase = (Math.sin(t * 2.5) * 0.5 + 0.5) * 0.4;
      emissiveColor.lerp(amberColors.bright, flarePhase);
      emissiveIntensity = 0.9 + flarePhase * 0.4;
    }

    matRef.current.color.lerp(baseColor, 0.08);
    matRef.current.emissive.lerp(emissiveColor, 0.08);
    matRef.current.emissiveIntensity = THREE.MathUtils.lerp(
      matRef.current.emissiveIntensity,
      emissiveIntensity,
      0.08
    );

    // Organic breathing scale oscillation
    const breathScale = 1.0 + Math.sin(t * 1.6) * 0.045;
    const finalScale = (activated ? 1.08 : 1.0) * breathScale * (1 + voiceEnergy * 0.15);
    coreRef.current.scale.setScalar(finalScale);

    // Smooth spherical finish with subtle organic distortion
    const targetDistort = activeWeight > 0.3 ? 0.22 : 0.08;
    matRef.current.distort = THREE.MathUtils.lerp(matRef.current.distort, targetDistort + voiceEnergy * 0.2, 0.08);
    matRef.current.speed = THREE.MathUtils.lerp(matRef.current.speed, 0.8 + voiceEnergy * 2.0, 0.08);

    // Outer ambient glow halo
    if (glowRef.current) {
      glowRef.current.scale.setScalar(finalScale * 1.38);
      const glowColor = silverColors.glow.clone().lerp(amberColors.glow, activeWeight);
      glowRef.current.material.color.copy(glowColor);
      glowRef.current.material.opacity = THREE.MathUtils.lerp(0.08, 0.18, activeWeight) + Math.sin(t * 1.6) * 0.02 + voiceEnergy * 0.08;
    }

    // Point lights color sync
    if (lightRef.current) {
      lightRef.current.color.copy(silverColors.bright.clone().lerp(amberColors.bright, activeWeight));
      lightRef.current.intensity = 1.4 + Math.sin(t * 1.6) * 0.2 + voiceEnergy * 0.6;
    }
    if (lightRef2.current) {
      lightRef2.current.color.copy(silverColors.mid.clone().lerp(amberColors.mid, activeWeight));
    }
  });

  return (
    <group position={position}>
      {/* Outer ambient glow sphere */}
      <Sphere ref={glowRef} args={[1.45, 32, 32]}>
        <meshBasicMaterial
          color="#b0b0be"
          transparent
          opacity={0.09}
          side={THREE.BackSide}
        />
      </Sphere>

      {/* Main reflective Halo Core Sphere */}
      <Sphere ref={coreRef} args={[0.92, 64, 64]}>
        <MeshDistortMaterial
          ref={matRef}
          color="#b5b5bd"
          emissive="#484850"
          emissiveIntensity={0.35}
          roughness={0.16}
          metalness={0.82}
          distort={0.08}
          speed={0.8}
        />
      </Sphere>

      {/* Synchronized Point Lights for rich specular reflections */}
      <pointLight ref={lightRef} color="#dcdce4" intensity={1.4} distance={6} position={[1, 1.5, 2]} />
      <pointLight ref={lightRef2} color="#787882" intensity={0.8} distance={8} position={[-1.5, -1, 1]} />
    </group>
  );
}
