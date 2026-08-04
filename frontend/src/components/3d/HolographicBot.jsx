import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Float, Sphere, Torus, MeshDistortMaterial } from "@react-three/drei";
import * as THREE from "three";

export function HolographicBot({ isListening = false, activeBot = null }) {
  const coreRef = useRef();
  const outerShellRef = useRef();
  const ring1Ref = useRef();
  const ring2Ref = useRef();
  const ring3Ref = useRef();

  useFrame((state, delta) => {
    const t = state.clock.getElapsedTime();

    // Rotate core and shell
    if (coreRef.current) {
      coreRef.current.rotation.y = t * 0.4;
      coreRef.current.rotation.x = Math.sin(t * 0.2) * 0.2;
    }

    if (outerShellRef.current) {
      outerShellRef.current.rotation.y = -t * 0.2;
      outerShellRef.current.rotation.z = t * 0.15;
    }

    // Rotate orbital rings at varying speeds
    if (ring1Ref.current) {
      ring1Ref.current.rotation.x = t * 0.8;
      ring1Ref.current.rotation.y = t * 0.5;
    }
    if (ring2Ref.current) {
      ring2Ref.current.rotation.x = Math.sin(t * 0.5) * 1.5;
      ring2Ref.current.rotation.z = t * 0.6;
    }
    if (ring3Ref.current) {
      ring3Ref.current.rotation.y = -t * 0.7;
      ring3Ref.current.rotation.z = Math.cos(t * 0.4) * 1.2;
    }
  });

  // Dynamic colors based on bot status
  const primaryColor = activeBot ? "#06b6d4" : "#8b5cf6"; // Cyan vs Violet
  const secondaryColor = isListening ? "#10b981" : "#ec4899"; // Emerald vs Pink

  return (
    <Float speed={2.5} rotationIntensity={0.5} floatIntensity={0.8}>
      <group scale={1.2}>
        {/* Inner Glowing Core */}
        <Sphere ref={coreRef} args={[1, 64, 64]}>
          <MeshDistortMaterial
            color={primaryColor}
            emissive={primaryColor}
            emissiveIntensity={0.6}
            roughness={0.1}
            metalness={0.8}
            distort={0.35}
            speed={2}
            radius={1}
          />
        </Sphere>

        {/* Outer Wireframe Shell */}
        <Sphere ref={outerShellRef} args={[1.25, 24, 24]}>
          <meshStandardMaterial
            color={secondaryColor}
            wireframe
            transparent
            opacity={0.35}
            emissive={secondaryColor}
            emissiveIntensity={0.4}
          />
        </Sphere>

        {/* Orbital Ring 1 */}
        <Torus ref={ring1Ref} args={[1.6, 0.02, 16, 100]}>
          <meshBasicMaterial color="#38bdf8" transparent opacity={0.7} />
        </Torus>

        {/* Orbital Ring 2 */}
        <Torus ref={ring2Ref} args={[1.9, 0.015, 16, 100]}>
          <meshBasicMaterial color="#a78bfa" transparent opacity={0.6} />
        </Torus>

        {/* Orbital Ring 3 */}
        <Torus ref={ring3Ref} args={[2.2, 0.01, 16, 100]}>
          <meshBasicMaterial color="#f472b6" transparent opacity={0.5} />
        </Torus>

        {/* Center Point Light */}
        <pointLight color={primaryColor} intensity={2.5} distance={8} />
      </group>
    </Float>
  );
}
