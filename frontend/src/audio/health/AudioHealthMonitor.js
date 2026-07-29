/**
 * Audio Health Monitor — monitors runtime audio quality.
 *
 * Emits structured events but does NOT control conversation flow.
 */
import { getAudioMetrics } from "../metrics/AudioMetrics.js";

export class AudioHealthMonitor {
  constructor() {
    this._metrics = getAudioMetrics();
    this._alerts = [];
    this._listeners = new Set();
    this._checkInterval = null;
    this._silenceStart = null;
    this._config = {
      clippingThreshold: 0.98,
      silenceThreshold: 0.005,
      silenceAlertMs: 10000,
      maxQueueDepth: 150,
      checkIntervalMs: 2000,
    };
  }

  start(config = {}) {
    Object.assign(this._config, config);
    this._checkInterval = setInterval(() => this._check(), this._config.checkIntervalMs);
  }

  stop() {
    if (this._checkInterval) {
      clearInterval(this._checkInterval);
      this._checkInterval = null;
    }
  }

  onAlert(listener) {
    this._listeners.add(listener);
    return () => this._listeners.delete(listener);
  }

  _emit(alert) {
    this._alerts.push({ ...alert, timestamp: Date.now() });
    if (this._alerts.length > 100) this._alerts.shift();
    for (const listener of this._listeners) {
      try { listener(alert); } catch (_) {}
    }
  }

  /**
   * Called by the audio pipeline on each processed frame.
   */
  checkFrame(samples) {
    if (!samples || samples.length === 0) return;

    // Clipping detection
    let peak = 0;
    for (let i = 0; i < samples.length; i++) {
      const abs = Math.abs(samples[i]);
      if (abs > peak) peak = abs;
    }
    if (peak > this._config.clippingThreshold) {
      this._emit({ type: "clipping", severity: "warning", peak });
    }
  }

  _check() {
    const micLevel = this._metrics.get("micLevel");
    const queueDepth = this._metrics.get("playbackBufferDepth");

    // Prolonged silence
    if (micLevel < this._config.silenceThreshold) {
      if (!this._silenceStart) this._silenceStart = Date.now();
      const silenceMs = Date.now() - this._silenceStart;
      if (silenceMs > this._config.silenceAlertMs) {
        this._emit({ type: "prolonged_silence", severity: "info", durationMs: silenceMs });
        this._silenceStart = Date.now(); // reset to avoid spam
      }
    } else {
      this._silenceStart = null;
    }

    // Queue overflow
    if (queueDepth > this._config.maxQueueDepth) {
      this._emit({ type: "queue_overflow", severity: "warning", depth: queueDepth });
    }
  }

  getAlerts(since = 0) {
    return this._alerts.filter((a) => a.timestamp > since);
  }

  snapshot() {
    return {
      activeAlerts: this._alerts.length,
      recentAlerts: this._alerts.slice(-10),
    };
  }
}

let _instance = null;
export function getAudioHealthMonitor() {
  if (!_instance) _instance = new AudioHealthMonitor();
  return _instance;
}
