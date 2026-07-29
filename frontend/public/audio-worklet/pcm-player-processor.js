/**
 * PCM Ring Buffer Player AudioWorklet
 *
 * Chunks arrive via MessagePort → written to ring buffer.
 * process() reads from ring buffer every128 samples.
 * Pre-buffers500ms before starting playback (absorbs all network jitter).
 * On underrun: holds last sample (no click, no silence).
 */
class PCMPlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._ringSize = 48000 * 5;
    this._ring = new Float32Array(this._ringSize);
    this._w = 0;
    this._r = 0;
    this._n = 0;
    this._on = false;
    this._play = false;
    this._last = 0;
    this._pre = 24000; // 500ms at 48kHz — large enough to absorb all jitter

    this.port.onmessage = (e) => {
      if (e.data.type === "chunk") {
        const s = new Int16Array(e.data.buffer);
        for (let i = 0; i < s.length; i++) {
          this._ring[this._w] = s[i] / 32768.0;
          this._w = (this._w + 1) % this._ringSize;
        }
        this._n = Math.min(this._n + s.length, this._ringSize);
        if (!this._play && this._n >= this._pre) this._play = true;
      } else if (e.data.type === "start") {
        this._on = true; this._play = false;
        this._w = 0; this._r = 0; this._n = 0; this._last = 0;
      } else if (e.data.type === "stop") {
        this._on = false; this._play = false;
      }
    };
  }

  process(_, outputs) {
    const o = outputs[0];
    if (!o || !o.length) return true;
    const fs = o[0].length, ch = o.length;

    if (!this._on || !this._play) {
      for (let c = 0; c < ch; c++) o[c].fill(0);
      return true;
    }

    for (let i = 0; i < fs; i++) {
      let v;
      if (this._n > 0) {
        v = this._ring[this._r];
        this._r = (this._r + 1) % this._ringSize;
        this._n--;
        this._last = v;
      } else {
        v = this._last; // hold — no click
      }
      for (let c = 0; c < ch; c++) o[c][i] = v;
    }
    return true;
  }
}

registerProcessor("pcm-player", PCMPlayerProcessor);
