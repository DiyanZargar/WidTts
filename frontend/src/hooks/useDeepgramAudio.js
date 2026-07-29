import { useRef, useCallback } from "react";
import { createMicStream, stopMicStream, playAudioBuffer, StreamingAudioPlayer } from "../utils/audioUtils";

export function useDeepgramAudio() {
  const micRef = useRef(null);
  const audioContextRef = useRef(null);
  const currentSourceRef = useRef(null);
  const pendingResolveRef = useRef(null);
  const streamingPlayerRef = useRef(null);

  const getAudioContext = () => {
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
    }
    return audioContextRef.current;
  };

  const startMic = useCallback(async (onChunk) => {
    try {
      micRef.current = await createMicStream(onChunk);
      return micRef.current;
    } catch (err) {
      console.warn("Microphone access failed or omitted:", err);
      return null;
    }
  }, []);

  const stopMic = useCallback(() => {
    if (micRef.current) {
      stopMicStream(micRef.current);
      micRef.current = null;
    }
  }, []);

  const stopTTS = useCallback(() => {
    // Stop streaming player if active
    if (streamingPlayerRef.current) {
      try { streamingPlayerRef.current.stop(); } catch (_) {}
      streamingPlayerRef.current = null;
    }
    // Stop legacy AudioBufferSourceNode if active
    if (currentSourceRef.current) {
      try { currentSourceRef.current.stop(); } catch (_) {}
      currentSourceRef.current = null;
    }
    // Resolve any pending promise
    if (pendingResolveRef.current) {
      pendingResolveRef.current();
      pendingResolveRef.current = null;
    }
  }, []);

  /**
   * Legacy single-buffer playback (backward compatible).
   * Used when the backend sends a single ArrayBuffer (e.g., REST fallback).
   */
  const playTTS = useCallback(async (arrayBuffer) => {
    stopTTS();
    const source = await playAudioBuffer(arrayBuffer, getAudioContext());
    currentSourceRef.current = source;
    return new Promise((resolve) => {
      let resolved = false;
      const done = () => {
        if (!resolved) { resolved = true; resolve(); pendingResolveRef.current = null; }
      };
      pendingResolveRef.current = done;
      source.addEventListener("ended", done, { once: true });
      setTimeout(() => {
        if (!resolved) {
          console.warn("[TTS] Playback safety timeout triggered — forcing resolve");
          try { source.stop(); } catch (_) {}
          done();
        }
      }, 25_000);
    });
  }, [stopTTS]);

  /**
   * Start a streaming TTS playback session.
   * Returns a StreamingAudioPlayer instance that chunks can be appended to.
   */
  const startStreamingTTS = useCallback(async () => {
    stopTTS();
    const player = new StreamingAudioPlayer();
    streamingPlayerRef.current = player;
    await player.start();
    return player;
  }, [stopTTS]);

  return { startMic, stopMic, playTTS, stopTTS, startStreamingTTS };
}
