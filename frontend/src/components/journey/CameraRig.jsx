import { useRef, useMemo } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { useScroll } from '@react-three/drei';
import * as THREE from 'three';

/**
 * CameraRig — Drives camera along a CatmullRomCurve3 path using scroll offset.
 * 6 waypoints correspond to the 6 journey sections.
 * Damped lerp for smooth trailing, mouse parallax for liveliness.
 */
export function CameraRig() {
  const scroll = useScroll();
  const { camera, size } = useThree();
  const mouseRef = useRef({ x: 0, y: 0 });
  const currentPos = useRef(new THREE.Vector3(0, 0, 8));
  const currentLookAt = useRef(new THREE.Vector3(0, 0, 0));

  // 6 waypoints — camera path through the void
  const curve = useMemo(() => {
    return new THREE.CatmullRomCurve3([
      new THREE.Vector3(0, 0, 8),       // Section 1: Overview — far, looking at distant Core
      new THREE.Vector3(2, -8, 6),      // Section 2: LLM — slide right+down, closer
      new THREE.Vector3(-2, -16, 5),    // Section 3: Speech — slide left, deeper
      new THREE.Vector3(0, -24, 3),     // Section 4: Bot Identity — close on Core
      new THREE.Vector3(0, -32, 6),     // Section 5: Review — pull back, frame everything
      new THREE.Vector3(0, -40, 5),     // Section 6: Live — settled operational view
    ], false, 'catmullrom', 0.5);
  }, []);

  // Corresponding look-at targets
  const lookAtCurve = useMemo(() => {
    return new THREE.CatmullRomCurve3([
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(0, -8, 0),
      new THREE.Vector3(0, -16, 0),
      new THREE.Vector3(0, -24, 0),
      new THREE.Vector3(0, -32, 0),
      new THREE.Vector3(0, -40, 0),
    ], false, 'catmullrom', 0.5);
  }, []);

  // Track mouse for parallax
  useMemo(() => {
    const handler = (e) => {
      mouseRef.current.x = (e.clientX / window.innerWidth - 0.5) * 2;
      mouseRef.current.y = (e.clientY / window.innerHeight - 0.5) * 2;
    };
    window.addEventListener('mousemove', handler);
    return () => window.removeEventListener('mousemove', handler);
  }, []);

  useFrame(() => {
    const offset = scroll.offset; // 0 → 1

    // Target position from scroll
    const targetPos = curve.getPointAt(Math.min(offset, 0.999));
    const targetLookAt = lookAtCurve.getPointAt(Math.min(offset, 0.999));

    // Mouse parallax (±0.3 max offset)
    const parallaxX = mouseRef.current.x * 0.3;
    const parallaxY = -mouseRef.current.y * 0.2;

    targetPos.x += parallaxX;
    targetPos.y += parallaxY;

    // Damped lerp (§12.9 — factor 0.08–0.12)
    currentPos.current.lerp(targetPos, 0.1);
    currentLookAt.current.lerp(targetLookAt, 0.1);

    camera.position.copy(currentPos.current);
    camera.lookAt(currentLookAt.current);
  });

  return null;
}
