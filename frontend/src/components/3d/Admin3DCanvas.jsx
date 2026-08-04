import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { HolographicBot } from "./HolographicBot";
import { ParticleField } from "./ParticleField";

export function Admin3DCanvas({ activeBot, isListening }) {
  return (
    <div className="w-full h-72 md:h-96 rounded-2xl overflow-hidden relative border border-cyan-500/20 bg-gradient-to-b from-slate-950/80 via-slate-900/50 to-slate-950/80 shadow-2xl backdrop-blur-xl group">
      {/* 3D Scene Overlay UI */}
      <div className="absolute top-4 left-4 z-10 flex items-center gap-3 bg-black/40 backdrop-blur-md px-4 py-2 rounded-xl border border-white/10">
        <span className="relative flex h-3 w-3">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-3 w-3 bg-cyan-500"></span>
        </span>
        <span className="text-xs font-semibold tracking-wider text-cyan-300 uppercase">
          3D Holographic Core
        </span>
      </div>

      <div className="absolute bottom-4 right-4 z-10 text-xs text-slate-400 bg-black/40 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10 pointer-events-none opacity-70 group-hover:opacity-100 transition-opacity">
        🖱️ Drag to rotate • Scroll to zoom
      </div>

      {/* R3F Canvas */}
      <Canvas
        camera={{ position: [0, 0, 6], fov: 45 }}
        gl={{ antialias: true, alpha: true }}
      >
        {/* Lighting */}
        <ambientLight intensity={0.5} />
        <directionalLight position={[5, 5, 5]} intensity={1.2} color="#ffffff" />
        <pointLight position={[-5, -5, -5]} intensity={0.8} color="#c084fc" />

        {/* Floating Holographic Avatar */}
        <HolographicBot activeBot={activeBot} isListening={isListening} />

        {/* Ambient Floating Particles */}
        <ParticleField count={400} />

        {/* Orbit Controls with bounds */}
        <OrbitControls
          enableZoom={true}
          minDistance={3.5}
          maxDistance={9}
          enablePan={false}
          autoRotate={true}
          autoRotateSpeed={0.8}
        />
      </Canvas>
    </div>
  );
}
