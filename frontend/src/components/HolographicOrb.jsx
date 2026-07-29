import React, { useContext, useEffect, useRef, useState } from "react";
import { ConversationContext } from "../context/ConversationContext";
import { audioVolumeTracker } from "../utils/audioUtils";

export default function HolographicOrb({ onOpenSession }) {
  const { state } = useContext(ConversationContext);
  const containerRef = useRef(null);
  const coreRef = useRef(null);
  const outerRingRef = useRef(null);
  const midRingRef = useRef(null);
  const innerRingRef = useRef(null);

  const [tilt, setTilt] = useState({ x: 0, y: 0 });

  // Map state to colors & themes
  const getOrbState = () => {
    if (!state.isOpen) return "closed";
    if (state.status === "connecting") return "connecting";
    if (state.status === "completed") return "completed";
    if (state.status === "cancelled") return "disconnected";
    if (state.isSpeaking) return "speaking";
    if (state.isListening) return "listening";
    if (state.status === "active") return "thinking";
    return "idle";
  };

  const orbState = getOrbState();

  // Mouse tilt parallax effect
  const handleMouseMove = (e) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left - rect.width / 2;
    const y = e.clientY - rect.top - rect.height / 2;
    
    // Max 15 degrees tilt
    const tiltX = (y / (rect.height / 2)) * -12;
    const tiltY = (x / (rect.width / 2)) * 12;
    setTilt({ x: tiltX, y: tiltY });
  };

  const handleMouseLeave = () => {
    setTilt({ x: 0, y: 0 });
  };

  // Real-time animation loop reading raw AnalyserNode values
  useEffect(() => {
    let rafId;
    const updateVisuals = () => {
      const vol = Math.max(audioVolumeTracker.mic, audioVolumeTracker.speaker);
      
      // Select elements to distort
      if (coreRef.current && outerRingRef.current && midRingRef.current && innerRingRef.current) {
        // Base scale depends on state
        let baseScale = 1;
        let brightness = 1;
        
        if (orbState === "speaking") {
          baseScale = 1.05 + (vol / 120);
          brightness = 1.1 + (vol / 80);
        } else if (orbState === "listening") {
          baseScale = 1.02 + (vol / 150);
          brightness = 1.0 + (vol / 100);
        } else if (orbState === "thinking") {
          // Subtle breathing while thinking
          baseScale = 1.0 + Math.sin(Date.now() / 200) * 0.03;
          brightness = 1.0 + Math.sin(Date.now() / 200) * 0.1;
        } else if (orbState === "idle") {
          // Standard idle breathing
          baseScale = 1.0 + Math.sin(Date.now() / 800) * 0.02;
          brightness = 0.9 + Math.sin(Date.now() / 800) * 0.05;
        }

        // Apply visual updates to core
        coreRef.current.style.transform = `scale(${baseScale})`;
        coreRef.current.style.filter = `brightness(${brightness})`;

        // Distort rings
        const outerScale = 1 + (vol / 90) * 0.15;
        const midScale = 1 + (vol / 110) * 0.1;
        const innerScale = 1 + (vol / 130) * 0.05;

        outerRingRef.current.style.transform = `rotate(${Date.now() / 60}deg) scale(${outerScale})`;
        midRingRef.current.style.transform = `rotate(${-Date.now() / 45}deg) scale(${midScale})`;
        innerRingRef.current.style.transform = `rotate(${Date.now() / 30}deg) scale(${innerScale})`;

        // Glow opacity
        outerRingRef.current.style.opacity = orbState === "listening" ? 0.8 : 0.4 + (vol / 100) * 0.4;
      }
      
      rafId = requestAnimationFrame(updateVisuals);
    };

    updateVisuals();
    return () => cancelAnimationFrame(rafId);
  }, [orbState]);

  // Determine styles for different states
  const getGlowColor = () => {
    switch (orbState) {
      case "closed":
        return "from-zinc-500/20 to-transparent shadow-zinc-500/10";
      case "connecting":
        return "from-amber-500/20 to-transparent shadow-amber-500/15";
      case "listening":
        return "from-cyan-500/30 to-transparent shadow-cyan-500/25";
      case "speaking":
        return "from-blue-500/30 to-transparent shadow-blue-500/25";
      case "thinking":
        return "from-purple-500/30 to-transparent shadow-purple-500/20";
      case "completed":
        return "from-green-500/30 to-transparent shadow-green-500/20";
      case "disconnected":
        return "from-red-500/20 to-transparent shadow-red-500/15";
      default:
        return "from-zinc-600/15 to-transparent shadow-zinc-600/10";
    }
  };

  const getCoreGradient = () => {
    switch (orbState) {
      case "closed":
        return "bg-[radial-gradient(circle_at_30%_30%,#27272a_0%,#09090b_100%)]";
      case "connecting":
        return "bg-[radial-gradient(circle_at_30%_30%,#f59e0b_0%,#78350f_50%,#09090b_100%)]";
      case "listening":
        return "bg-[radial-gradient(circle_at_30%_30%,#22d3ee_0%,#0891b2_40%,#09090b_100%)]";
      case "speaking":
        return "bg-[radial-gradient(circle_at_30%_30%,#60a5fa_0%,#2563eb_40%,#09090b_100%)]";
      case "thinking":
        return "bg-[radial-gradient(circle_at_30%_30%,#c084fc_0%,#7c3aed_40%,#09090b_100%)]";
      case "completed":
        return "bg-[radial-gradient(circle_at_30%_30%,#4ade80_0%,#16a34a_40%,#09090b_100%)]";
      case "disconnected":
        return "bg-[radial-gradient(circle_at_30%_30%,#f87171_0%,#dc2626_50%,#09090b_100%)]";
      default:
        return "bg-[radial-gradient(circle_at_30%_30%,#3f3f46_0%,#18181b_50%,#09090b_100%)]";
    }
  };

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className="relative flex items-center justify-center cursor-pointer transition-transform duration-300 ease-out select-none"
      style={{
        width: "420px",
        height: "420px",
        transform: `perspective(1000px) rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`,
      }}
      onClick={!state.isOpen ? onOpenSession : undefined}
    >
      {/* 1. Large ambient background glow behind the widget */}
      <div 
        className={`absolute inset-0 rounded-full bg-gradient-to-b ${getGlowColor()} filter blur-[60px] opacity-80 transition-all duration-700`}
      />

      {/* 2. Concentric ring visualizers */}
      <div className="absolute inset-4 rounded-full border border-white/5 pointer-events-none" />

      {/* Outer Waveform Ring */}
      <div 
        ref={outerRingRef}
        className="absolute inset-8 rounded-full border-2 border-dashed border-cyan-500/20 transition-all duration-300 ease-out pointer-events-none"
        style={{ transformOrigin: "center" }}
      />

      {/* Middle Pulse Ring */}
      <div 
        ref={midRingRef}
        className="absolute inset-16 rounded-full border border-purple-500/20 transition-all duration-300 ease-out pointer-events-none"
        style={{ 
          transformOrigin: "center",
          borderStyle: "double",
          borderWidth: "3px" 
        }}
      />

      {/* Inner frequency Ring */}
      <div 
        ref={innerRingRef}
        className="absolute inset-24 rounded-full border border-white/10 transition-all duration-300 ease-out pointer-events-none"
        style={{ transformOrigin: "center" }}
      />

      {/* 3. Outer Glassmorphism Shell */}
      <div className="absolute inset-28 rounded-full glass-orb p-4 flex items-center justify-center transition-all duration-500">
        
        {/* Inner Glass Layer */}
        <div className="w-full h-full rounded-full bg-black/40 flex items-center justify-center overflow-hidden relative">
          
          {/* Subtle reflection overlay */}
          <div className="absolute inset-0 bg-gradient-to-tr from-transparent via-white/5 to-white/10 pointer-events-none" />
          
          {/* 4. Living AI Core */}
          <div
            ref={coreRef}
            className={`w-[120px] h-[120px] rounded-full transition-all duration-500 ease-out flex items-center justify-center relative shadow-[0_0_50px_-5px_rgba(0,0,0,0.8)] ${getCoreGradient()}`}
          >
            {/* Dynamic inner energy pattern (rotates in CSS) */}
            <div className="absolute inset-0 rounded-full bg-[radial-gradient(circle_at_70%_70%,rgba(255,255,255,0.15)_0%,transparent_50%)] animate-energy mix-blend-screen" />
            
            {/* Tiny floating dust inside core (rendered only in active modes) */}
            {(orbState === "thinking" || orbState === "speaking" || orbState === "listening") && (
              <div className="absolute inset-2 rounded-full border border-white/5 animate-spin duration-[15s]" />
            )}
          </div>

        </div>

      </div>

      {/* Resting state "Click to interact" floating prompt */}
      {!state.isOpen && (
        <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 text-center pointer-events-none">
          <span className="text-zinc-500 text-xs font-semibold tracking-[0.2em] uppercase transition-all hover:text-zinc-400">
            Initialize Core
          </span>
          <div className="w-1.5 h-1.5 rounded-full bg-zinc-500/40 mx-auto mt-2 animate-ping" />
        </div>
      )}
    </div>
  );
}
