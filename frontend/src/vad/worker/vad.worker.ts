// vad.worker.ts — VAD Worker: dual-engine orchestration + state machine
//
// Runs SileroVAD (ONNX) and WebRTCVAD (energy) in parallel.
// Receives PCM frames from AudioWorklet → runs inference →
// manages state machine → emits events to main thread.

import { WebRTCVAD } from "../engines/WebRTCVAD";
import { SileroVAD } from "../engines/SileroVAD";
import { PreRollBuffer } from "../buffers/PreRollBuffer";
import { VADStateMachine, VADState } from "../VADStateMachine";

// ── Worker State ──

let webrtcEngine: WebRTCVAD | null = null;
let sileroEngine: SileroVAD | null = null;
let stateMachine: VADStateMachine | null = null;
let preRollBuffer: PreRollBuffer | null = null;
let isReady = false;
let ttsPlaying = false;
let droppedFrames = 0;
let totalFrames = 0;

// ── Configuration ──

interface VADInitConfig {
  modelUrl: string;
  sampleRate: number;
  frameDurationMs: number;
  preRollMs: number;
  adaptiveThresholds: boolean;
  gateDeepgram: boolean;
  minSpeechDurationMs: number;
  minSilenceDurationMs: number;
  speechStartTimeoutMs: number;
  cooldownMs: number;
  startThreshold: number;
  continueThreshold: number;
}

// ── Event posting ──

function postEvent(
  event: string,
  extra: Record<string, unknown> = {}
): void {
  (self as any).postMessage({
    type: "event",
    event,
    timestamp: Date.now(),
    ...extra,
  });
}

function postMetrics(metrics: Record<string, unknown>): void {
  (self as any).postMessage({ type: "metrics", ...metrics });
}

// ── Frame processing ──

function processFrame(pcm: Float32Array, frameTimestamp: number): void {
  if (!webrtcEngine || !sileroEngine || !stateMachine || !preRollBuffer) return;

  totalFrames++;

  // Always push to pre-roll buffer
  preRollBuffer.push(pcm);

  // Fast WebRTC check first
  const webrtcResult = webrtcEngine.processFrame(pcm);
  const isWebrtcSpeech = webrtcResult > 0.5;

  // Silero inference (async handled by the worker's async proxy)
  // For responsiveness: use cached/next-frame Silero result
  // Silero probability is computed asynchronously and stored
  const sileroProb = (_pendingSileroProb !== undefined ? _pendingSileroProb : 0.0);

  // Schedule next Silero inference
  scheduleSileroInference(pcm);

  // Process through state machine
  stateMachine.process(isWebrtcSpeech, sileroProb, ttsPlaying, frameTimestamp);
}

// ── Silero async inference ──

let _pendingSileroProb = 0.0;
let _sileroInferencePending = false;

async function scheduleSileroInference(frame: Float32Array): Promise<void> {
  if (_sileroInferencePending || !sileroEngine) return;
  _sileroInferencePending = true;

  try {
    _pendingSileroProb = await sileroEngine.processFrameAsync(frame);
  } catch (e) {
    console.warn("[VAD Worker] Silero inference failed:", e);
    _pendingSileroProb = 0.0;
  } finally {
    _sileroInferencePending = false;
  }
}

// ── Message handlers ──

self.onmessage = async (e: MessageEvent) => {
  const msg = e.data;

  switch (msg.type) {
    case "init": {
      const config = msg as VADInitConfig;
      try {
        preRollBuffer = new PreRollBuffer(config.preRollMs, config.frameDurationMs);

        // Initialize dual engines
        webrtcEngine = new WebRTCVAD();
        sileroEngine = new SileroVAD();

        const [webrtcOk, sileroOk] = await Promise.all([
          webrtcEngine.initialize(),
          sileroEngine.initialize({ modelUrl: config.modelUrl }),
        ]);

        let fallbackEngines: string[] = [];
        if (!sileroOk) fallbackEngines.push("SileroVAD");
        if (!webrtcOk) fallbackEngines.push("WebRTCVAD");

        // State machine
        stateMachine = new VADStateMachine({
          minSpeechDurationMs: config.minSpeechDurationMs,
          minSilenceDurationMs: config.minSilenceDurationMs,
          speechStartTimeoutMs: config.speechStartTimeoutMs,
          cooldownMs: config.cooldownMs,
        });

        // Wire callbacks
        stateMachine.onSpeechStart = () => {
          postEvent("speech_start", {
            probability: _pendingSileroProb,
            adaptiveThreshold: stateMachine!.startThreshold,
            noiseFloor: stateMachine!.noiseFloor,
          });
        };

        stateMachine.onSpeechEnd = () => {
          postEvent("speech_end", {
            durationMs: stateMachine!.speechDurationMs,
            framesProcessed: totalFrames,
          });
        };

        stateMachine.onInterruption = () => {
          postEvent("interruption", {
            probability: _pendingSileroProb,
            ttsPlaying: true,
          });
        };

        stateMachine.onStateChange = (_state: VADState) => {
          // Optionally debug state transitions
        };

        if (fallbackEngines.length > 0) {
          if (fallbackEngines.length === 2) {
            // Both failed — pass-through mode
            postEvent("fallback", {
              failedEngines: fallbackEngines.join(","),
              mode: "passthrough",
            });
            isReady = false;
          } else {
            // Single engine active
            postEvent("fallback", {
              failedEngines: fallbackEngines.join(","),
              mode: "single-engine",
            });
            isReady = true;
          }
        } else {
          isReady = true;
          postEvent("vad_ready", {});
        }
      } catch (e: any) {
        postEvent("fallback", {
          error: e?.message || "Unknown init error",
          mode: "passthrough",
        });
        isReady = false;
      }
      break;
    }

    case "frame": {
      // msg.pcm is transferred ArrayBuffer
      const pcmFloat32 = new Float32Array(msg.pcm);
      processFrame(pcmFloat32, Date.now());

      // Track dropped frames (if new frame arrives before previous processed)
      if (totalFrames > 0 && droppedFrames > 0) {
        const dropRate = droppedFrames / totalFrames;
        if (dropRate > 0.05) {
          postMetrics({
            droppedFrames,
            totalFrames,
            dropRate,
          });
        }
      }
      break;
    }

    case "config": {
      // Runtime config updates (thresholds, etc.)
      if (stateMachine && msg.ttsPlaying !== undefined) {
        ttsPlaying = msg.ttsPlaying;
      }
      break;
    }

    case "set_tts_playing": {
      ttsPlaying = msg.playing;
      break;
    }

    case "reset": {
      if (stateMachine) stateMachine.reset();
      if (preRollBuffer) preRollBuffer.clear();
      if (sileroEngine) sileroEngine.reset();
      if (webrtcEngine) webrtcEngine.reset();
      droppedFrames = 0;
      totalFrames = 0;
      break;
    }

    case "dispose": {
      if (sileroEngine) sileroEngine.dispose();
      if (webrtcEngine) webrtcEngine.dispose();
      sileroEngine = null;
      webrtcEngine = null;
      stateMachine = null;
      preRollBuffer = null;
      isReady = false;
      break;
    }
  }
};
