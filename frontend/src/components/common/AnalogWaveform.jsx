import React, { useEffect, useRef } from 'react';

/**
 * AnalogWaveform — Calm, organic analog harmonic signal line.
 *
 * Renders directly under the Halo Orb on a 2D Canvas at 60fps.
 * Driven by live microphone input via Web Audio AnalyserNode or fallback RMS levels.
 *
 * - Silence / Standby: A perfectly calm, serene, glowing reference line.
 * - Voice detected: Raises smoothly into harmonic sinusoidal analog waves
 *   (flowing crests and troughs matching analog Amplitude vs Time signals).
 */
export function AnalogWaveform({
  getMicAnalyser,
  getAudioAnalyser,
  active = false,
  haloState = 'idle',
  listenLevel = 0,
  audioLevel = 0,
  width = 380,
  height = 56,
}) {
  const canvasRef = useRef(null);
  const rafRef = useRef(null);
  const smoothedLevelRef = useRef(0);
  const phaseRef = useRef(0);

  // Store fast-updating props in a ref to avoid recreating the canvas and RAF loop 60 times/sec
  const propsRef = useRef({
    getMicAnalyser,
    getAudioAnalyser,
    active,
    haloState,
    listenLevel,
    audioLevel,
  });

  useEffect(() => {
    propsRef.current = {
      getMicAnalyser,
      getAudioAnalyser,
      active,
      haloState,
      listenLevel,
      audioLevel,
    };
  });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // High-DPI support for Retina displays
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    const bufferLength = 128;
    const timeData = new Uint8Array(bufferLength);

    const render = () => {
      rafRef.current = requestAnimationFrame(render);

      const {
        getMicAnalyser: getMic,
        getAudioAnalyser: getAudio,
        active: isActive,
        haloState: state,
        listenLevel: lLevel,
        audioLevel: aLevel,
      } = propsRef.current;

      // Read audio energy from mic analyser (fallback to listenLevel/audioLevel)
      const micAnalyser = getMic?.();
      const audioAnalyser = getAudio?.();
      const analyser = micAnalyser || (state === 'speaking' ? audioAnalyser : null);

      let targetRms = 0;

      if (isActive && analyser) {
        try {
          analyser.getByteTimeDomainData(timeData);
          let sum = 0;
          for (let i = 0; i < bufferLength; i++) {
            const val = (timeData[i] - 128) / 128;
            sum += val * val;
          }
          targetRms = Math.sqrt(sum / bufferLength);
        } catch {
          targetRms = 0;
        }
      } else if (isActive) {
        targetRms = state === 'speaking' ? aLevel : lLevel;
      }

      // Calm envelope smoothing: responsive attack (0.22) & organic decay (0.08)
      const attack = 0.22;
      const decay = 0.08;
      if (targetRms > smoothedLevelRef.current) {
        smoothedLevelRef.current += (targetRms - smoothedLevelRef.current) * attack;
      } else {
        smoothedLevelRef.current += (targetRms - smoothedLevelRef.current) * decay;
      }

      const amp = smoothedLevelRef.current;

      // Calm phase progression (slow fluid speed + slight increase when speaking)
      phaseRef.current += 0.035 + amp * 0.04;
      const phase = phaseRef.current;

      // Clear canvas
      ctx.clearRect(0, 0, width, height);

      const midY = height / 2;
      const isVoiceDetected = amp > 0.005;

      // Colors matching Halo Orb state
      let mainColor = 'rgba(216, 216, 220, 0.45)';
      let glowColor = 'rgba(180, 180, 190, 0.18)';
      let coreColor = 'rgba(255, 255, 255, 0.85)';

      if (state === 'user_speaking' || (isVoiceDetected && state === 'listening')) {
        mainColor = 'rgba(240, 209, 144, 0.95)';
        glowColor = 'rgba(232, 199, 122, 0.45)';
        coreColor = 'rgba(253, 243, 220, 1.0)';
      } else if (state === 'speaking') {
        mainColor = 'rgba(243, 201, 110, 0.95)';
        glowColor = 'rgba(243, 201, 110, 0.45)';
        coreColor = 'rgba(255, 243, 214, 1.0)';
      } else if (state === 'thinking') {
        mainColor = 'rgba(185, 182, 221, 0.85)';
        glowColor = 'rgba(140, 132, 214, 0.35)';
        coreColor = 'rgba(231, 230, 245, 1.0)';
      } else if (state === 'connecting') {
        mainColor = 'rgba(220, 170, 92, 0.6)';
        glowColor = 'rgba(220, 170, 92, 0.25)';
        coreColor = 'rgba(255, 255, 255, 0.7)';
      }

      // Linear gradients across the width (smoothly anchors and fades at outer 10% edges)
      const grad = ctx.createLinearGradient(0, 0, width, 0);
      grad.addColorStop(0, 'rgba(255, 255, 255, 0)');
      grad.addColorStop(0.12, mainColor);
      grad.addColorStop(0.5, coreColor);
      grad.addColorStop(0.88, mainColor);
      grad.addColorStop(1, 'rgba(255, 255, 255, 0)');

      const glowGrad = ctx.createLinearGradient(0, 0, width, 0);
      glowGrad.addColorStop(0, 'rgba(255, 255, 255, 0)');
      glowGrad.addColorStop(0.15, glowColor);
      glowGrad.addColorStop(0.5, glowColor);
      glowGrad.addColorStop(0.85, glowColor);
      glowGrad.addColorStop(1, 'rgba(255, 255, 255, 0)');

      // If inactive or dead silent, draw peaceful flat baseline
      if (!isVoiceDetected) {
        ctx.save();
        ctx.beginPath();
        ctx.moveTo(0, midY);
        ctx.lineTo(width, midY);
        ctx.strokeStyle = grad;
        ctx.lineWidth = 1.4;
        ctx.shadowColor = glowColor;
        ctx.shadowBlur = isActive ? 6 : 3;
        ctx.stroke();
        ctx.restore();
        return;
      }

      // ─── CALM COMPOSITE SINE WAVE HARMONICS ───
      const maxPeak = Math.min((height / 2) - 3, 22);
      const voiceScale = Math.min(1, amp * 5.0);

      const numPoints = 120;
      const points = [];

      for (let i = 0; i <= numPoints; i++) {
        const norm = i / numPoints; // 0.0 to 1.0
        const x = norm * width;

        // Smooth window envelope: anchors to 0 at left and right ends, blooms in center
        const windowWeight = Math.sin(norm * Math.PI);
        const windowEnvelope = Math.pow(windowWeight, 1.4);

        // Superposition of 3 calm harmonics:
        const wave1 = Math.sin(norm * Math.PI * 7.0 - phase);
        const wave2 = Math.sin(norm * Math.PI * 11.0 + phase * 0.8) * 0.45;
        const wave3 = Math.sin(norm * Math.PI * 4.0 - phase * 0.5) * 0.25;

        const composite = (wave1 + wave2 + wave3) / 1.7;
        const y = midY + composite * maxPeak * voiceScale * windowEnvelope;
        points.push({ x, y });
      }

      // 1. Soft Ambient Glow Pass
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      for (let i = 1; i < points.length; i++) {
        const prev = points[i - 1];
        const curr = points[i];
        const xc = (prev.x + curr.x) / 2;
        const yc = (prev.y + curr.y) / 2;
        ctx.quadraticCurveTo(prev.x, prev.y, xc, yc);
      }
      ctx.lineTo(points[points.length - 1].x, points[points.length - 1].y);
      ctx.strokeStyle = glowGrad;
      ctx.lineWidth = 3.8;
      ctx.shadowColor = glowColor;
      ctx.shadowBlur = 10;
      ctx.stroke();
      ctx.restore();

      // 2. Primary Crisp Analog Beam
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      for (let i = 1; i < points.length; i++) {
        const prev = points[i - 1];
        const curr = points[i];
        const xc = (prev.x + curr.x) / 2;
        const yc = (prev.y + curr.y) / 2;
        ctx.quadraticCurveTo(prev.x, prev.y, xc, yc);
      }
      ctx.lineTo(points[points.length - 1].x, points[points.length - 1].y);
      ctx.strokeStyle = grad;
      ctx.lineWidth = 1.6;
      ctx.shadowColor = coreColor;
      ctx.shadowBlur = 4;
      ctx.stroke();
      ctx.restore();
    };

    render();

    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [width, height]);

  return (
    <div className="halo__waveform-wrapper">
      <canvas
        ref={canvasRef}
        className="halo__waveform-canvas"
        style={{ width: `${width}px`, height: `${height}px` }}
      />
    </div>
  );
}

