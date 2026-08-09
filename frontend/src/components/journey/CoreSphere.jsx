import { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { MeshDistortMaterial, Sphere } from '@react-three/drei';
import * as THREE from 'three';

/**
 * CoreSphere — The central distorted icosphere (Radiant Emerald Green Palette).
 * Present at every scroll depth, visually anchors the entire journey.
 * State progression: dim/dormant → partially lit → fully bright → flare on activation.
 *
 * Also reused on /user — import this, don't duplicate.
 */
export function CoreSphere({ progress = 0, activated = false, isActive = false, position = [0, 0, 0], status, audioLevel = 0, listenLevel = 0 }) {
  const coreRef = useRef();
  const glowRef = useRef();
  const matRef = useRef();

  // Emerald Green setup palette (Admin & Active User)
  const emeraldColors = useMemo(() => ({
    dim: new THREE.Color('hsl(165, 85%, 22%)'),
    mid: new THREE.Color('hsl(160, 90%, 42%)'),
    bright: new THREE.Color('hsl(155, 95%, 58%)'),
    bloom: new THREE.Color('hsl(150, 100%, 82%)'),
  }), []);

  // Soft Yellowish Amber for Inner Core when Inactive/Off
  const offColors = useMemo(() => ({
    dim: new THREE.Color('hsl(45, 75%, 18%)'),
    mid: new THREE.Color('hsl(45, 85%, 45%)'),
  }), []);

  const isUserPortal = status !== undefined;

  useFrame((state, delta) => {
    if (!coreRef.current || !matRef.current) return;
    const t = state.clock.getElapsedTime();

    // Gentle breathing rotation
    coreRef.current.rotation.y += delta * 0.15;
    coreRef.current.rotation.x = Math.sin(t * 0.1) * 0.1;

    // Combined voice amplitude
    const voiceEnergy = Math.max(audioLevel, listenLevel);

    const isClosed = isUserPortal && (!isActive || status === 'idle' || status === 'disconnected' || status === 'completed' || status === 'off' || status === 'cancelled' || status === 'error');

    let baseColor, emissiveColor, emissiveIntensity;

    if (isClosed) {
      // ONLY Inner Core shifts to Soft Yellowish Amber when Inactive/Off
      baseColor = offColors.dim.clone();
      emissiveColor = offColors.mid.clone();
      emissiveIntensity = 0.45;
    } else {
      // Active / Admin Mode: Default Radiant Emerald Green
      baseColor = emeraldColors.dim.clone();
      emissiveColor = emeraldColors.mid.clone();
      emissiveIntensity = 0.6;

      if (status === 'speaking') {
        emissiveColor.lerp(emeraldColors.bright, 0.4 + audioLevel * 0.5);
        emissiveIntensity = 0.7 + audioLevel * 0.8;
      } else if (status === 'listening') {
        emissiveColor.lerp(emeraldColors.bright, 0.3 + listenLevel * 0.4);
        emissiveIntensity = 0.6 + listenLevel * 0.6;
      } else if (status === 'thinking') {
        emissiveColor = emeraldColors.bloom.clone();
        emissiveIntensity = 1.0;
      } else if (progress < 0.5) {
        emissiveColor.lerp(emeraldColors.mid, progress * 2);
      } else {
        emissiveColor.copy(emeraldColors.mid).lerp(emeraldColors.bright, (progress - 0.5) * 2);
      }

      if (activated) {
        const flarePhase = (Math.sin(t * 2) * 0.5 + 0.5) * 0.3;
        emissiveColor.lerp(emeraldColors.bloom, flarePhase);
      }
    }

    matRef.current.color.lerp(baseColor, 0.08);
    matRef.current.emissive.lerp(emissiveColor, 0.08);
    matRef.current.emissiveIntensity = THREE.MathUtils.lerp(
      matRef.current.emissiveIntensity,
      emissiveIntensity,
      0.08
    );

    const baseDistort = isClosed ? 0.15 : status === 'thinking' ? 0.5 : voiceEnergy > 0.05 ? 0.4 : 0.3;
    matRef.current.distort = THREE.MathUtils.lerp(matRef.current.distort, baseDistort + voiceEnergy * 0.3, 0.1);
    matRef.current.speed = THREE.MathUtils.lerp(matRef.current.speed, isClosed ? 0.5 : 1.5 + voiceEnergy * 2.5, 0.1);

    const scale = (activated ? 1.05 : 1) * (1 + voiceEnergy * 0.15);
    coreRef.current.scale.setScalar(scale);

    // Outer ambient glow halo: 100% Transparent Delicate Admin Emerald Halo
    if (glowRef.current) {
      glowRef.current.scale.setScalar(scale * 1.35);
      glowRef.current.material.color.set('hsl(155, 95%, 58%)');
      glowRef.current.material.opacity = 0.05 + voiceEnergy * 0.08;
    }
  });

  return (
    <group position={position}>
      {/* Outer ambient glow sphere — Exact Admin Theme */}
      <Sphere ref={glowRef} args={[1.4, 32, 32]}>
        <meshBasicMaterial
          color="hsl(155, 95%, 58%)"
          transparent
          opacity={0.08}
          side={THREE.BackSide}
        />
      </Sphere>

      {/* Main distorted inner core sphere — Exact Admin Theme */}
      <Sphere ref={coreRef} args={[0.85, 64, 64]}>
        <MeshDistortMaterial
          ref={matRef}
          color="hsl(165, 85%, 22%)"
          emissive="hsl(160, 90%, 42%)"
          emissiveIntensity={0.6}
          roughness={0.2}
          metalness={0.8}
          distort={0.3}
          speed={1.5}
        />
      </Sphere>

      {/* Inner point lights */}
      <pointLight color="hsl(155, 95%, 58%)" intensity={1.5} distance={5} />
      <pointLight color="hsl(160, 90%, 42%)" intensity={0.8} distance={8} position={[0, -1, 0]} />
    </group>
  );
}
