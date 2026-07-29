// PreRollBuffer.ts — Circular buffer preventing phoneme clipping on speech onset
// Holds ~150ms of audio frames, flushed when speech is confirmed.

export class PreRollBuffer {
  private _frames: Float32Array[] = [];
  private _writeIdx = 0;
  private _capacity: number;

  /**
   * @param durationMs Duration of audio to buffer before speech onset (default 150ms)
   * @param frameDurationMs Duration of each frame (default 30ms)
   */
  constructor(durationMs = 150, frameDurationMs = 30) {
    this._capacity = Math.ceil(durationMs / frameDurationMs);
    // Pre-allocate slots
    for (let i = 0; i < this._capacity; i++) {
      this._frames.push(new Float32Array(0));
    }
  }

  /** Push a new frame into the buffer */
  push(frame: Float32Array): void {
    this._frames[this._writeIdx % this._capacity] = new Float32Array(frame);
    this._writeIdx++;
  }

  /** Return all buffered frames in chronological order and clear */
  flush(): Float32Array[] {
    const start = Math.max(0, this._writeIdx - this._capacity);
    const end = this._writeIdx;
    const result: Float32Array[] = [];
    for (let i = start; i < end; i++) {
      const frame = this._frames[i % this._capacity];
      if (frame.length > 0) {
        result.push(frame);
      }
    }
    this.clear();
    return result;
  }

  /** Clear buffer without returning frames */
  clear(): void {
    for (let i = 0; i < this._capacity; i++) {
      this._frames[i] = new Float32Array(0);
    }
    this._writeIdx = 0;
  }

  get frameCount(): number {
    return Math.min(this._writeIdx, this._capacity);
  }
}
