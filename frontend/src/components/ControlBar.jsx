import React, { useContext } from "react";
import { ConversationContext } from "../context/ConversationContext";
import { Power, Settings, Mic, MicOff } from "lucide-react";

export default function ControlBar({
  isMuted,
  onToggleMute,
  onOpenSettings,
  onCloseSession,
}) {
  const { state } = useContext(ConversationContext);

  if (!state.isOpen) return null;

  return (
    <div className="flex flex-col items-center gap-6 mt-8 animate-fade-in">
      {/* 1. Primary interaction state prompt */}
      <div className="flex flex-col items-center gap-1.5 text-center">
        <span className="text-zinc-500 text-[10px] tracking-[0.3em] font-semibold uppercase">
          AI Link Status
        </span>
        <span
          className={`text-xs font-medium tracking-wide uppercase transition-all duration-300 ${
            state.status === "connecting"
              ? "text-amber-400 text-glow-purple"
              : state.isSpeaking
              ? "text-blue-400 text-glow-cyan"
              : state.isListening
              ? "text-cyan-400 text-glow-cyan"
              : state.status === "completed"
              ? "text-green-400 text-glow-green"
              : state.status === "active"
              ? "text-purple-400 text-glow-purple"
              : "text-zinc-400"
          }`}
        >
          {state.status === "connecting" && "Synchronizing Link..."}
          {state.status === "active" && !state.isSpeaking && !state.isListening && "Core Processing..."}
          {state.isSpeaking && "Assisting..."}
          {state.isListening && (isMuted ? "Mic Standby (Muted)" : "Awaiting Input...")}
          {state.status === "completed" && "Core Complete"}
          {state.status === "cancelled" && "Link Cancelled"}
        </span>
      </div>

      {/* 2. Micro-utility control shelf */}
      <div className="flex items-center gap-8 px-8 py-3 rounded-full bg-white/[0.02] border border-white/[0.05] backdrop-blur-md shadow-2xl transition-all hover:bg-white/[0.04]">
        
        {/* Toggle Mute */}
        <button
          onClick={onToggleMute}
          title={isMuted ? "Unmute Mic" : "Mute Mic"}
          className={`p-2.5 rounded-full transition-all duration-200 hover:scale-110 active:scale-95 ${
            isMuted 
              ? "text-red-400 bg-red-500/10 border border-red-500/20" 
              : "text-zinc-400 hover:text-white"
          }`}
        >
          {isMuted ? <MicOff size={16} /> : <Mic size={16} />}
        </button>

        {/* Configuration settings panel */}
        <button
          onClick={onOpenSettings}
          title="Conversation Packs"
          className="p-2.5 rounded-full text-zinc-400 hover:text-white transition-all duration-200 hover:scale-110 active:scale-95"
        >
          <Settings size={16} />
        </button>

        {/* Terminate session */}
        <button
          onClick={onCloseSession}
          title="Disconnect Session"
          className="p-2.5 rounded-full text-zinc-400 hover:text-red-400 hover:bg-red-500/10 border border-transparent hover:border-red-500/10 transition-all duration-200 hover:scale-110 active:scale-95"
        >
          <Power size={16} />
        </button>

      </div>
    </div>
  );
}
