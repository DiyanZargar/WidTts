/**
 * Audio Pipeline Configuration — centralized, observable, runtime-updateable.
 *
 * All audio processing modules consume this config instead of hardcoded values.
 * Supports runtime updates without changing component implementations.
 */
export const DEFAULT_AUDIO_CONFIG = {
  // Browser DSP
  echoCancellation: true,
  noiseSuppression: true,
  autoGainControl: true,

  // RNNoise
  enableRNNoise: true,

  // High-pass filter
  enableHighPass: true,
  highPassCutoff: 80, // Hz

  // Noise gate
  enableNoiseGate: true,
  noiseGateAttack: 0.01,    // seconds
  noiseGateRelease: 0.1,    // seconds
  noiseGateHold: 0.15,      // seconds

  // VAD
  vadSensitivity: 0.5,      // 0-1
  vadFrameSize: 512,        // samples

  // Pre-roll
  preRollDuration: 200,     // ms

  // Hangover (how long to keep streaming after speech ends)
  hangoverDuration: 300,    // ms

  // General
  sampleRate: 48000,
  frameSize: 480,           // samples (10ms at 48kHz)

  // Playback
  playbackBufferSize: 5,    // seconds of ring buffer
  maxQueueChunks: 200,
};

class AudioConfig {
  constructor(overrides = {}) {
    this._config = { ...DEFAULT_AUDIO_CONFIG, ...overrides };
    this._listeners = new Set();
  }

  get(key) {
    return this._config[key];
  }

  getAll() {
    return { ...this._config };
  }

  /**
   * Update one or more config values at runtime.
   * Notifies all listeners so components can react.
   */
  update(partial) {
    const changed = {};
    for (const [key, value] of Object.entries(partial)) {
      if (key in this._config && this._config[key] !== value) {
        changed[key] = { old: this._config[key], new: value };
        this._config[key] = value;
      }
    }
    if (Object.keys(changed).length > 0) {
      for (const listener of this._listeners) {
        try { listener(changed); } catch (_) {}
      }
    }
  }

  /**
   * Subscribe to config changes. Returns unsubscribe function.
   */
  onChange(listener) {
    this._listeners.add(listener);
    return () => this._listeners.delete(listener);
  }

  /**
   * Create a snapshot for diagnostics.
   */
  snapshot() {
    return { ...this._config };
  }
}

// Singleton
let _instance = null;

export function getAudioConfig(overrides) {
  if (!_instance) _instance = new AudioConfig(overrides);
  return _instance;
}

export { AudioConfig };
