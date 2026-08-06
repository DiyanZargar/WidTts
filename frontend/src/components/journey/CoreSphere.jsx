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
export function CoreSphere({ progress = 0, activated = false, position = [0, 0, 0], status, audioLevel = 0 }) {
  const coreRef = useRef();
  const glowRef = useRef();

  // Radiant Emerald Green color progression based on setup progress (0→1)
  const colors = useMemo(() => ({
    dim: new THREE.Color('hsl(165, 85%, 22%)'),
    mid: new THREE.Color('hsl(160, 90%, 42%)'),
    bright: new THREE.Color('hsl(155, 95%, 58%)'),
    bloom: new THREE.Color('hsl(150, 100%, 82%)'),
    warn: new THREE.Color('hsl(28, 85%, 58%)'),
  }), []);

  // Status-to-color mapping for /user mode
  const STATUS_COLOR = useMemo(() => ({
    idle: colors.dim,
    connecting: colors.mid,
    listening: colors.mid,
    thinking: colors.bright,
    speaking: colors.bright,
    error: colors.warn,
  }), [colors]);

  useFrame((state) => {
    if (!coreRef.current) return;
    const t = state.clock.getElapsedTime();

    // Gentle breathing rotation
    coreRef.current.rotation.y = t * 0.15;
    coreRef.current.rotation.x = Math.sin(t * 0.1) * 0.1;

    // Determine target color
    let baseColor;

    if (status) {
      // /user mode — driven by voice session status
      baseColor = (STATUS_COLOR[status] || colors.dim).clone();
      if (status === 'speaking' && audioLevel > 0) {
        baseColor.lerp(colors.bloom, audioLevel * 0.3);
      }
    } else {
      // Admin mode — driven by setup progress
      baseColor = colors.dim.clone();
      if (progress < 0.5) {
        baseColor.lerp(colors.mid, progress * 2);
      } else {
        baseColor.copy(colors.mid).lerp(colors.bright, (progress - 0.5) * 2);
      }

      if (activated) {
        const flarePhase = (Math.sin(t * 2) * 0.5 + 0.5) * 0.3;
        baseColor.lerp(colors.bloom, flarePhase);
      }
    }

    coreRef.current.material.color.lerp(baseColor, 0.05);
    coreRef.current.material.emissive.lerp(baseColor, 0.05);

    // Audio reactivity / setup pulse
    const reactiveScale = status === 'speaking' ? 1 + audioLevel * 0.15 : 1;
    const scale = (activated ? 1.05 : 1) * reactiveScale;
    coreRef.current.scale.setScalar(scale);

    // Outer glow pulse
    if (glowRef.current) {
      glowRef.current.scale.setScalar(scale * 1.35);
      glowRef.current.material.opacity = (0.08 + (progress * 0.1) + (audioLevel * 0.15));
    }
  });

  return (
    <group position={position}>
      {/* Outer ambient glow sphere */}
      <Sphere ref={glowRef} args={[1.4, 32, 32]}>
        <meshBasicMaterial
          color="hsl(155, 95%, 58%)"
          transparent
          opacity={0.08}
          side={THREE.BackSide}
        />
      </Sphere>

      {/* Main distorted core sphere */}
      <Sphere ref={coreRef} args={[1.1, 64, 64]}>
        <MeshDistortMaterial
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
