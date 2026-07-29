import React, { useContext, useEffect, useRef } from "react";
import { ConversationContext } from "../context/ConversationContext";

export default function TranscriptOverlay() {
  const { state } = useContext(ConversationContext);
  const containerRef = useRef(null);

  // Auto-scroll transcript container if overflow occurs
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [state.transcriptLines, state.partialTranscript]);

  if (!state.isOpen) return null;

  // Build list of active lines including the real-time partial transcript
  const displayLines = [...state.transcriptLines];
  if (state.partialTranscript) {
    displayLines.push({
      id: "partial",
      speaker: "user",
      text: state.partialTranscript,
      isPartial: true,
    });
  }

  // Restrict display to the last 4 statements
  const visibleLines = displayLines.slice(-4);

  return (
    <div className="w-full max-w-2xl px-6 my-4 select-text">
      <div
        ref={containerRef}
        className="flex flex-col gap-6 text-center max-h-[220px] overflow-y-auto pr-1 transition-all duration-300"
      >
        {visibleLines.length === 0 ? (
          <div className="text-zinc-600 text-xs tracking-wider uppercase italic py-4 animate-pulse">
            Establishing communication neural link...
          </div>
        ) : (
          visibleLines.map((line, idx) => {
            const isLatest = idx === visibleLines.length - 1;
            
            // Progressive fading for older lines
            let opacityClass = "opacity-20";
            if (isLatest) opacityClass = "opacity-100";
            else if (idx === visibleLines.length - 2) opacityClass = "opacity-60";
            else if (idx === visibleLines.length - 3) opacityClass = "opacity-35";

            const speakerLabel = line.speaker === "assistant" ? "AI" : "YOU";

            return (
              <div
                key={line.id}
                className={`flex flex-col items-center gap-1 transition-all duration-500 transform ${
                  isLatest ? "scale-100" : "scale-95"
                } ${opacityClass}`}
              >
                {/* Minimalist sender tag */}
                <span 
                  className={`text-[9px] font-bold tracking-[0.25em] uppercase ${
                    line.speaker === "assistant" 
                      ? "text-blue-400/80" 
                      : "text-cyan-400/80"
                  }`}
                >
                  {speakerLabel}
                </span>

                {/* Subtitle text with glow for the latest message */}
                <p
                  className={`text-lg md:text-xl font-light tracking-wide max-w-lg leading-relaxed ${
                    line.speaker === "assistant"
                      ? isLatest
                        ? "text-white text-glow-cyan"
                        : "text-zinc-300"
                      : isLatest
                      ? "text-cyan-200 text-glow-cyan italic"
                      : "text-zinc-400 italic"
                  }`}
                >
                  {line.text}
                  {line.isPartial && <span className="animate-pulse">...</span>}
                </p>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
