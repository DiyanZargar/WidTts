/**
 * Playback Queue Manager — owns queue lifecycle and buffering.
 *
 * Separates playback responsibilities:
 *   Queue Manager → queue lifecycle, buffering, overflow
 *   Player → only renders audio
 */
import { getAudioConfig } from "../config/AudioConfig.js";
import { getAudioMetrics } from "../metrics/AudioMetrics.js";

export class PlaybackQueueManager {
  constructor() {
    this._queue = [];
    this._config = getAudioConfig();
    this._metrics = getAudioMetrics();
    this._maxSize = this._config.get("maxQueueChunks") || 200;
    this._droppedChunks = 0;
    this._totalEnqueued = 0;
    this._totalDequeued = 0;
  }

  enqueue(chunk) {
    if (!chunk || chunk.byteLength === 0) return false;

    if (this._queue.length >= this._maxSize) {
      // Overflow: drop oldest chunk
      this._queue.shift();
      this._droppedChunks++;
      this._metrics.incrementDroppedFrames();
    }

    this._queue.push(chunk);
    this._totalEnqueued++;
    this._metrics.setPlaybackBufferDepth(this._queue.length);
    return true;
  }

  dequeue() {
    const chunk = this._queue.shift();
    if (chunk) {
      this._totalDequeued++;
      this._metrics.setPlaybackBufferDepth(this._queue.length);
    }
    return chunk;
  }

  peek() {
    return this._queue.length > 0 ? this._queue[0] : null;
  }

  clear() {
    const cleared = this._queue.length;
    this._queue = [];
    this._metrics.setPlaybackBufferDepth(0);
    return cleared;
  }

  removeStale(maxAgeMs = 5000) {
    // Remove chunks older than maxAgeMs (for interruption cleanup)
    const cutoff = Date.now() - maxAgeMs;
    const before = this._queue.length;
    this._queue = this._queue.filter((c) => (c._enqueuedAt || Infinity) > cutoff);
    const removed = before - this._queue.length;
    if (removed > 0) this._metrics.setPlaybackBufferDepth(this._queue.length);
    return removed;
  }

  get size() { return this._queue.length; }
  get isEmpty() { return this._queue.length === 0; }
  get droppedChunks() { return this._droppedChunks; }

  snapshot() {
    return {
      size: this._queue.length,
      maxSize: this._maxSize,
      droppedChunks: this._droppedChunks,
      totalEnqueued: this._totalEnqueued,
      totalDequeued: this._totalDequeued,
    };
  }
}
