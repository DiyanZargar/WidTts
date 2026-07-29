/**
 * Streaming Flow Controller — explicit flow control for audio streaming.
 *
 * Implements:
 *   - configurable max queue size
 *   - queue backpressure
 *   - overflow detection
 *   - stale chunk removal
 *   - interruption cleanup
 *   - queue reset
 *   - graceful overflow recovery
 *
 * Prevents unlimited memory growth under slow playback conditions.
 */
import { getAudioConfig } from "../config/AudioConfig.js";
import { getAudioMetrics } from "../metrics/AudioMetrics.js";

export class FlowController {
  constructor() {
    this._config = getAudioConfig();
    this._metrics = getAudioMetrics();
    this._paused = false;
    this._overflowCount = 0;
    this._backpressureActive = false;
    this._listeners = new Set();
  }

  /**
   * Check if the producer should pause (backpressure).
   * Returns true if the queue is approaching capacity.
   */
  shouldPause(currentQueueSize) {
    const maxSize = this._config.get("maxQueueChunks") || 200;
    const threshold = maxSize * 0.8; // 80% full

    if (currentQueueSize >= threshold && !this._backpressureActive) {
      this._backpressureActive = true;
      this._emit("backpressure_on", { queueSize: currentQueueSize });
    }

    return currentQueueSize >= threshold;
  }

  /**
   * Check if backpressure should be released.
   */
  shouldResume(currentQueueSize) {
    const maxSize = this._config.get("maxQueueChunks") || 200;
    const threshold = maxSize * 0.5; // 50% full

    if (currentQueueSize <= threshold && this._backpressureActive) {
      this._backpressureActive = false;
      this._emit("backpressure_off", { queueSize: currentQueueSize });
      return true;
    }

    return currentQueueSize <= threshold;
  }

  /**
   * Handle queue overflow — returns number of chunks to drop.
   */
  handleOverflow(currentQueueSize, incomingCount) {
    const maxSize = this._config.get("maxQueueChunks") || 200;
    const overflow = (currentQueueSize + incomingCount) - maxSize;

    if (overflow > 0) {
      this._overflowCount++;
      this._metrics.incrementDroppedFrames(overflow);
      this._emit("overflow", { overflow, queueSize: currentQueueSize });
      return overflow;
    }
    return 0;
  }

  /**
   * Reset flow controller state (e.g. on interruption).
   */
  reset() {
    this._paused = false;
    this._backpressureActive = false;
    this._emit("reset", {});
  }

  /**
   * Clean up stale chunks after interruption.
   */
  cleanupAfterInterruption(queueManager) {
    const removed = queueManager.removeStale(1000); // remove chunks > 1s old
    this.reset();
    this._emit("interruption_cleanup", { removed });
    return removed;
  }

  onEvent(listener) {
    this._listeners.add(listener);
    return () => this._listeners.delete(listener);
  }

  _emit(type, data) {
    for (const listener of this._listeners) {
      try { listener({ type, ...data, timestamp: Date.now() }); } catch (_) {}
    }
  }

  snapshot() {
    return {
      paused: this._paused,
      backpressureActive: this._backpressureActive,
      overflowCount: this._overflowCount,
    };
  }
}
