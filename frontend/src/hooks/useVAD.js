// useVAD.js — Hybrid VAD hook using @ricky0123/vad-web (Silero V5 ONNX)
//
// Uses MicVAD which handles AudioContext, AudioWorklet, Worker, and ONNX
// runtime internally. Provides speech start/end callbacks for TTS interruption.
// Falls back gracefully if VAD initialization fails.

import { useRef, useCallback, useEffect } from "react";

const DEFAULT_OPTIONS = {
  // Silero model: "v5" (latest) or "legacy" (v4)
  model: "v5",
  // Speech threshold (0-1). Higher = less sensitive.
  positiveSpeechThreshold: 0.75,
  negativeSpeechThreshold: 0.55,
  // Grace period after speech end before firing onSpeechEnd (ms)
  redemptionMs: 300,
  // Minimum speech duration to consider valid (ms)
  minSpeechMs: 250,
  // Audio prepended to speech segment (ms)
  preSpeechPadMs: 150,
  // Submit partial speech on pause
  submitUserSpeechOnPause: false,
  // Base path for ONNX WASM files (served from public/)
  baseAssetPath: "/",
  onnxWASMBasePath: "/ort-wasm/",
  // Auto-start on load
  startOnLoad: false,
};

export function useVAD({ onSpeechStart, onSpeechEnd, onInterruption, onFrameProcessed }) {
  const micVADRef = useRef(null);
  const isReadyRef = useRef(false);
  const ttsPlayingRef = useRef(false);
  const fallbackRef = useRef(false);

  const start = useCallback(
    async (stream) => {
      if (micVADRef.current) return; // Already started

      try {
        // Dynamically import vad-web (browser-only, avoids SSR issues)
        const { MicVAD } = await import("@ricky0123/vad-web");

        const vad = await MicVAD.new({
          ...DEFAULT_OPTIONS,
          getStream: async () => stream,
          pauseStream: async (s) => {
            // Don't actually pause — we need continuous audio
          },
          resumeStream: async (s) => s,
          // ── Callbacks ──
          onFrameProcessed: (probs, _frame) => {
            if (onFrameProcessed) {
              onFrameProcessed({
                probability: probs.isSpeech,
                timestamp: Date.now(),
              });
            }
          },
          onSpeechStart: () => {
            const prob = 1.0; // MicVAD doesn't expose per-frame prob in callback
            console.log(
              `[PIPELINE] ${new Date().toISOString()} VAD_SPEECH_START | prob=${prob.toFixed(3)}`
            );
            if (ttsPlayingRef.current) {
              console.log(
                `[PIPELINE] ${new Date().toISOString()} VAD_INTERRUPTION_TRIGGERED | ttsPlaying=true`
              );
              onInterruption?.({ probability: prob });
            } else {
              onSpeechStart?.({ probability: prob });
            }
          },
          onSpeechEnd: (audio) => {
            const durMs = audio ? Math.round((audio.length / 16000) * 1000) : 0;
            console.log(
              `[PIPELINE] ${new Date().toISOString()} VAD_SPEECH_END | dur_ms=${durMs}`
            );
            onSpeechEnd?.({ durationMs: durMs });
          },
          onVADMisfire: () => {
            console.log(
              `[PIPELINE] ${new Date().toISOString()} VAD_MISFIRE`
            );
          },
        });

        micVADRef.current = vad;

        // Start listening
        await vad.start();
        isReadyRef.current = true;
        console.log("[useVAD] Hybrid VAD active (Silero V5 ONNX)");
      } catch (e) {
        fallbackRef.current = true;
        console.warn(
          `[PIPELINE] ${new Date().toISOString()} VAD_FALLBACK_ACTIVATED | error=${e?.message || "init_failed"}`
        );
        console.warn("[useVAD] VAD initialization failed — continuing without speech detection");
      }
    },
    [onSpeechStart, onSpeechEnd, onInterruption, onFrameProcessed]
  );

  const setTTSPlaying = useCallback((playing) => {
    ttsPlayingRef.current = playing;
    if (micVADRef.current) {
      // MicVAD continues running; interruption is handled in onSpeechStart
    }
  }, []);

  const stop = useCallback(() => {
    if (micVADRef.current) {
      try {
        micVADRef.current.destroy();
      } catch (_) {}
      micVADRef.current = null;
    }
    isReadyRef.current = false;
    fallbackRef.current = false;
    console.log("[useVAD] VAD stopped");
  }, []);

  return {
    start,
    stop,
    setTTSPlaying,
    isReady: () => isReadyRef.current,
    isFallback: () => fallbackRef.current,
  };
}
