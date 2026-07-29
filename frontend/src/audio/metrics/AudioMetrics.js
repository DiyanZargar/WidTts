/**
 * Runtime Audio Metrics — observability-only metrics collection.
 *
 * Does NOT affect runtime behavior. Reports structured metrics
 * for diagnostics and monitoring.
 */
export class AudioMetrics {
  constructor() {
    this._metrics = {
      micLevel: 0,
      estimatedNoise: 0,
      speechDetectionCount: 0,
      falseVADActivations: 0,
      totalUtteranceDurationMs: 0,
      utteranceCount: 0,
      interruptionCount: 0,
      droppedFrames: 0,
      playbackBufferDepth: 0,
      queueLatencyMs: 0,
      sttConfidence: 0,
      preprocessingLatencyMs: 0,
      ttsChunksSent: 0,
      ttsChunksReceived: 0,
      sttPartialCount: 0,
      sttFinalCount: 0,
      connectionResets: 0,
    };
    this._sessionStart = Date.now();
    this._snapshots = [];
  }

  // ── Setters (called by audio pipeline components) ──

  setMicLevel(level) { this._metrics.micLevel = level; }
  setEstimatedNoise(noise) { this._metrics.estimatedNoise = noise; }
  incrementSpeechDetections() { this._metrics.speechDetectionCount++; }
  incrementFalseVAD() { this._metrics.falseVADActivations++; }
  addUtteranceDuration(ms) {
    this._metrics.totalUtteranceDurationMs += ms;
    this._metrics.utteranceCount++;
  }
  incrementInterruptions() { this._metrics.interruptionCount++; }
  incrementDroppedFrames(n = 1) { this._metrics.droppedFrames += n; }
  setPlaybackBufferDepth(depth) { this._metrics.playbackBufferDepth = depth; }
  setQueueLatency(ms) { this._metrics.queueLatencyMs = ms; }
  setSttConfidence(conf) { this._metrics.sttConfidence = conf; }
  setPreprocessingLatency(ms) { this._metrics.preprocessingLatencyMs = ms; }
  incrementTtsChunksSent() { this._metrics.ttsChunksSent++; }
  incrementTtsChunksReceived() { this._metrics.ttsChunksReceived++; }
  incrementSttPartials() { this._metrics.sttPartialCount++; }
  incrementSttFinals() { this._metrics.sttFinalCount++; }
  incrementConnectionResets() { this._metrics.connectionResets++; }

  // ── Getters ──

  get snapshot() {
    return {
      ...this._metrics,
      sessionDurationMs: Date.now() - this._sessionStart,
      avgUtteranceDurationMs: this._metrics.utteranceCount > 0
        ? Math.round(this._metrics.totalUtteranceDurationMs / this._metrics.utteranceCount)
        : 0,
    };
  }

  get(key) {
    return this._metrics[key];
  }

  reset() {
    for (const key of Object.keys(this._metrics)) {
      this._metrics[key] = 0;
    }
    this._sessionStart = Date.now();
  }
}

let _instance = null;
export function getAudioMetrics() {
  if (!_instance) _instance = new AudioMetrics();
  return _instance;
}
