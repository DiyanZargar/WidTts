import React from "react";
import { X } from "lucide-react";

const PACKS = [
  {
    id: "daily_life_companion",
    name: "Daily Life Companion",
    description: "Personal check-ins, routine discussions, and mood tracking.",
    color: "from-cyan-500/20 to-blue-500/10 border-cyan-500/20",
  },
  {
    id: "career_life_advisor",
    name: "Career & Life Advisor",
    description: "Explore career objectives, growth paths, and balance.",
    color: "from-purple-500/20 to-pink-500/10 border-purple-500/20",
  },
  {
    id: "health_wellness_assistant",
    name: "Health & Wellness",
    description: "Daily habit tracking, exercise, and wellness optimization.",
    color: "from-emerald-500/20 to-teal-500/10 border-emerald-500/20",
  },
  {
    id: "travel_planner",
    name: "Travel Planner",
    description: "Custom adventure recommendations and itinerary structures.",
    color: "from-amber-500/20 to-orange-500/10 border-amber-500/20",
  },
];

export default function SettingsPanel({
  isOpen,
  onClose,
  activeType,
  onChangeType,
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md p-6 animate-fade-in">
      <div 
        className="w-full max-w-md rounded-3xl glass-panel p-8 border border-white/10 relative overflow-hidden flex flex-col gap-6"
        style={{
          boxShadow: "inset 0 0 30px rgba(255,255,255,0.02), 0 25px 50px -12px rgba(0,0,0,0.8)"
        }}
      >
        {/* Glow accent */}
        <div className="absolute -top-24 -left-24 w-48 h-48 rounded-full bg-cyan-500/10 filter blur-[40px] pointer-events-none" />
        <div className="absolute -bottom-24 -right-24 w-48 h-48 rounded-full bg-purple-500/10 filter blur-[40px] pointer-events-none" />

        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/5 pb-4 relative">
          <div>
            <h3 className="text-base font-semibold tracking-wider text-white uppercase">
              AI Core Packs
            </h3>
            <p className="text-[10px] text-zinc-500 tracking-wide mt-1">
              Select a conversation matrix file
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-full text-zinc-400 hover:text-white hover:bg-white/5 transition-all"
          >
            <X size={16} />
          </button>
        </div>

        {/* Core list */}
        <div className="flex flex-col gap-3 relative overflow-y-auto max-h-[350px] pr-1">
          {PACKS.map((pack) => {
            const isActive = pack.id === activeType;

            return (
              <button
                key={pack.id}
                onClick={() => {
                  onChangeType(pack.id);
                  onClose();
                }}
                className={`w-full text-left p-4 rounded-2xl bg-gradient-to-br border transition-all duration-300 flex flex-col gap-1 relative overflow-hidden group ${
                  isActive 
                    ? `${pack.color} border-white/20 shadow-[0_0_20px_rgba(255,255,255,0.02)]`
                    : "from-white/[0.01] to-transparent border-white/[0.03] hover:border-white/10 hover:bg-white/[0.02]"
                }`}
              >
                {/* Active indicator dot */}
                {isActive && (
                  <div className="absolute top-4 right-4 w-2 h-2 rounded-full bg-white animate-pulse" />
                )}

                <span className={`text-sm font-semibold tracking-wide transition-all ${
                  isActive ? "text-white" : "text-zinc-300 group-hover:text-white"
                }`}>
                  {pack.name}
                </span>
                
                <span className="text-[11px] text-zinc-500 font-light leading-relaxed">
                  {pack.description}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
