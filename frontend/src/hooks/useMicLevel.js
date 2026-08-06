import { useEffect, useRef, useState } from 'react';

/**
 * useMicLevel — client-side AnalyserNode on the active mic stream.
 * Returns normalized mic input amplitude (0-1) for STT voice reactivity.
 */
export function useMicLevel(stream) {
  const [level, setLevel] = useState(0);
  const frameRef = useRef(null);

  useEffect(() => {
    if (!stream) {
      setLevel(0);
      return;
    }

    let ctx;
    let source;
    let analyser;
    try {
      ctx = new (window.AudioContext || window.webkitAudioContext)();
      if (ctx.state === 'suspended') {
        ctx.resume().catch(() => {});
      }
      source = ctx.createMediaStreamSource(stream);
      analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.6;
      source.connect(analyser);

      const data = new Uint8Array(analyser.frequencyBinCount);

      const tick = () => {
        analyser.getByteFrequencyData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i++) {
          sum += data[i];
        }
        const avg = sum / data.length / 255;
        // Boost responsiveness for STT mic input
        setLevel(Math.min(1, avg * 3.5));
        frameRef.current = requestAnimationFrame(tick);
      };
      tick();
    } catch (e) {
      console.warn('[useMicLevel] Error setting up mic analyser:', e);
    }

    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
      if (source) {
        try { source.disconnect(); } catch (_) {}
      }
      if (ctx) {
        try { ctx.close(); } catch (_) {}
      }
    };
  }, [stream]);

  return level;
}
