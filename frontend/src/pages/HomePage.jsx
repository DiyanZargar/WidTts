import React, { useContext, useEffect, useState } from "react";
import { ConversationContext } from "../context/ConversationContext";
import { useWebSocket } from "../hooks/useWebSocket";
import HolographicOrb from "../components/HolographicOrb";
import ControlBar from "../components/ControlBar";
import TranscriptOverlay from "../components/TranscriptOverlay";
import SettingsPanel from "../components/SettingsPanel";

export default function HomePage() {
  const { state, dispatch } = useContext(ConversationContext);
  const [conversationType, setConversationType] = useState("daily_life_companion");
  const [isMuted, setIsMuted] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  // Sync React mute state to the window level checked by useWebSocket mic stream
  useEffect(() => {
    window.widgetIsMuted = isMuted;
  }, [isMuted]);

  const { connect, disconnect } = useWebSocket(conversationType);

  // Connection manager lifecycle sync: connect when open, disconnect when closed
  useEffect(() => {
    if (state.isOpen) {
      connect();
    } else {
      disconnect();
    }
    return () => {
      disconnect();
    };
  }, [state.isOpen, connect, disconnect]);

  // Restores core back to sleeping state
  const handleCloseSession = () => {
    disconnect();
    sessionStorage.removeItem("widget_session_id");
    dispatch({ type: "CLOSE_WIDGET" });
    setIsMuted(false);
  };

  // Restarts session after completion or upon user request
  const handleRestartSession = () => {
    disconnect();
    sessionStorage.removeItem("widget_session_id");
    dispatch({ type: "RESET_FOR_NEW_SESSION" });
    setIsMuted(false);
    setTimeout(() => {
      connect();
    }, 50);
  };

  // Change conversation pack ID and trigger clean session re-handshake
  const handleChangeType = (newType) => {
    setConversationType(newType);
    disconnect();
    sessionStorage.removeItem("widget_session_id");
    dispatch({ type: "RESET_FOR_NEW_SESSION" });
  };

  const handleOpenSession = () => {
    dispatch({ type: "OPEN_WIDGET" });
  };

  // Get human readable active pack name
  const getPackName = () => {
    switch (conversationType) {
      case "daily_life_companion":
        return "Daily Life Companion";
      case "career_life_advisor":
        return "Career & Life Advisor";
      case "health_wellness_assistant":
        return "Health & Wellness Matrix";
      case "travel_planner":
        return "Travel Planner";
      default:
        return "Custom Core";
    }
  };

  // Static properties for background cinematic dust drift
  const particles = Array.from({ length: 25 }).map((_, i) => ({
    id: i,
    left: `${Math.random() * 100}%`,
    delay: `${Math.random() * 20}s`,
    size: `${Math.random() * 3 + 1}px`,
    duration: `${Math.random() * 15 + 20}s`,
  }));

  return (
    <div className="relative w-full h-full min-h-screen bg-[#09090B] flex flex-col justify-between items-center py-8 px-6 overflow-hidden">
      
      {/* 1. Ambient Volumetric Glow spots */}
      <div className="absolute top-1/4 left-1/4 w-[400px] h-[400px] rounded-full bg-cyan-600/5 filter blur-[100px] pointer-events-none bg-glow-1" />
      <div className="absolute bottom-1/4 right-1/4 w-[450px] h-[450px] rounded-full bg-purple-600/5 filter blur-[120px] pointer-events-none bg-glow-2" />

      {/* 2. Floating dust particle layer */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {particles.map((p) => (
          <div
            key={p.id}
            className="particle"
            style={{
              left: p.left,
              width: p.size,
              height: p.size,
              animationDelay: p.delay,
              animationDuration: p.duration,
            }}
          />
        ))}
      </div>

      {/* 3. Header HUD minimal tags */}
      <header className="w-full flex justify-between items-center max-w-6xl z-10 select-none">
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] font-bold tracking-[0.4em] text-white/40 uppercase">
            Aether AI Link
          </span>
          <span className="text-[8px] tracking-[0.2em] text-zinc-600 uppercase">
            System V2.9.4
          </span>
        </div>

        <div className="flex flex-col items-end gap-0.5">
          <span className="text-[10px] font-semibold tracking-widest text-zinc-400 uppercase">
            {getPackName()}
          </span>
          <span className="text-[8px] tracking-wider text-zinc-600 uppercase">
            Matrix Loaded
          </span>
        </div>
      </header>

      {/* 4. Central Hero Experience (Holographic Orb & Subtitles) */}
      <main className="flex-1 flex flex-col items-center justify-center w-full max-w-4xl z-10 gap-2">
        <HolographicOrb
          onOpenSession={handleOpenSession}
          onCloseSession={handleCloseSession}
          onRestartSession={handleRestartSession}
        />
        <TranscriptOverlay />
      </main>

      {/* 5. Minimal footer controls */}
      <footer className="w-full flex justify-center z-10">
        <ControlBar
          isMuted={isMuted}
          onToggleMute={() => setIsMuted(!isMuted)}
          onOpenSettings={() => setShowSettings(true)}
          onCloseSession={handleCloseSession}
        />
      </footer>

      {/* 6. Configuration Settings drawer */}
      <SettingsPanel
        isOpen={showSettings}
        onClose={() => setShowSettings(false)}
        activeType={conversationType}
        onChangeType={handleChangeType}
      />
    </div>
  );
}
