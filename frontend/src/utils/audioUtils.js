export const audioVolumeTracker = {
  mic: 0, speaker: 0, isTTSPlaying: false, _interrupted: false,
};

export function setTTSPlaying(playing) {
  audioVolumeTracker.isTTSPlaying = playing;
  if (!playing) audioVolumeTracker._interrupted = false;
}
export function wasInterrupted() { return audioVolumeTracker._interrupted; }
export function clearInterrupted() { audioVolumeTracker._interrupted = false; }

/* ═══════════════════════════════════════════════════════════════════
   Streaming Audio Player — gapless scheduled playback.

   Uses _nextPlayTime scheduling: each chunk is scheduled to start at
   the exact time the previous chunk ends, eliminating micro-gaps.
   Chunks are queued and scheduled via AudioBufferSourceNode.start(time).
   ═══════════════════════════════════════════════════════════════════ */

export class StreamingAudioPlayer {
  constructor(sampleRate = 48000) {
    this._sampleRate = sampleRate;
    this._audioContext = null;
    this._queue = [];
    this._pendingChunks = [];  // raw bytes buffered before start() completes
    this._nextPlayTime = 0;
    this._stopped = false;
    this._ended = false;
    this._endedCallbacks = [];
    this._currentSource = null;
    this._totalSamples = 0;
  }

  async start() {
    this._stopped = false;
    this._ended = false;
    this._nextPlayTime = 0;
    this._queue = [];
    this._pendingChunks = [];
    this._endedCallbacks = [];
    this._currentSource = null;
    this._totalSamples = 0;
    this._audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: this._sampleRate });
    if (this._audioContext.state === "suspended") await this._audioContext.resume();

    // Create analyser for speaker volume tracking
    this._analyser = this._audioContext.createAnalyser();
    this._analyser.fftSize = 256;
    this._analyser.connect(this._audioContext.destination);
    this._analyserData = new Uint8Array(this._analyser.frequencyBinCount);
    this._rafId = null;
    this._startVolumeTracking();

    // Flush any chunks that arrived while AudioContext was initializing
    for (const raw of this._pendingChunks) {
      this._appendRaw(raw);
    }
    this._pendingChunks = [];
  }

  _startVolumeTracking() {
    const poll = () => {
      if (!this._analyser || this._stopped) {
        audioVolumeTracker.speaker = 0;
        return;
      }
      this._analyser.getByteFrequencyData(this._analyserData);
      let sum = 0;
      for (let i = 0; i < this._analyserData.length; i++) sum += this._analyserData[i];
      audioVolumeTracker.speaker = sum / this._analyserData.length;
      this._rafId = requestAnimationFrame(poll);
    };
    poll();
  }

  _stopVolumeTracking() {
    if (this._rafId) {
      cancelAnimationFrame(this._rafId);
      this._rafId = null;
    }
    audioVolumeTracker.speaker = 0;
  }

  appendChunk(chunk) {
    if (!chunk || chunk.byteLength === 0 || this._stopped) return;

    // If endStream was called but new chunks arrived, reset ended state
    // (another TTS stream is starting — continue playing seamlessly)
    if (this._ended) {
      this._ended = false;
      this._endedCallbacks = [];
    }

    if (!this._audioContext) {
      // AudioContext not ready yet — buffer raw chunk for later
      this._pendingChunks.push(chunk instanceof Uint8Array ? chunk : new Uint8Array(chunk));
      return;
    }
    this._appendRaw(chunk);
  }

  _appendRaw(chunk) {
    const bytes = chunk instanceof Uint8Array ? chunk : new Uint8Array(chunk);
    const numSamples = bytes.byteLength / 2;
    this._totalSamples += numSamples;

    // Convert Int16 → Float32
    const int16 = new Int16Array(bytes.buffer, bytes.byteOffset, numSamples);
    const float32 = new Float32Array(numSamples);
    for (let i = 0; i < numSamples; i++) float32[i] = int16[i] / 32768.0;

    const buf = this._audioContext.createBuffer(1, numSamples, this._sampleRate);
    buf.getChannelData(0).set(float32);

    this._queue.push(buf);

    this._scheduleQueued();
  }

  _scheduleQueued() {
    if (this._stopped || !this._audioContext) return;

    while (this._queue.length > 0) {
      const buf = this._queue.shift();
      const src = this._audioContext.createBufferSource();
      src.buffer = buf;
      src.connect(this._analyser || this._audioContext.destination);

      const now = this._audioContext.currentTime;
      // On first chunk, start immediately; otherwise chain to previous end
      if (this._nextPlayTime <= now) {
        this._nextPlayTime = now;
      }
      src.start(this._nextPlayTime);
      this._nextPlayTime += buf.duration;

      this._currentSource = src;
    }

    // Schedule end-of-stream callback after last chunk finishes
    if (this._ended && this._currentSource) {
      this._currentSource.addEventListener("ended", () => {
        this._fireCallbacks();
      }, { once: true });
    }
  }

  endStream() {
    if (this._ended) return;
    this._ended = true;
    // Re-enter scheduling to attach ended listener on last source
    this._scheduleQueued();
    // If no audio was scheduled at all and no chunks are buffered, fire immediately
    // (pendingChunks means start() hasn't completed yet — start() will handle the ended listener)
    if (!this._currentSource && this._queue.length === 0 && this._pendingChunks.length === 0) {
      this._fireCallbacks();
    }
  }

  _fireCallbacks() {
    this._endedCallbacks.forEach((cb) => cb());
    this._endedCallbacks = [];
  }

  onEnded(callback) { this._endedCallbacks.push(callback); }

  stop() {
    this._stopped = true;
    this._ended = true;
    this._queue = [];
    this._stopVolumeTracking();
    if (this._currentSource) {
      try { this._currentSource.stop(); } catch (_) {}
      this._currentSource = null;
    }
    if (this._analyser) {
      try { this._analyser.disconnect(); } catch (_) {}
      this._analyser = null;
    }
    if (this._audioContext && this._audioContext.state !== "closed") {
      this._audioContext.close().catch(() => {});
    }
    this._audioContext = null;
    this._fireCallbacks();
  }
}

/* ═══════════════════════════════════════════════════════════════════
   Microphone Capture
   ═══════════════════════════════════════════════════════════════════ */

let micContext = null, micAnalyser = null, micSource = null, micRafId = null;

function trackMicVolume(stream) {
  try {
    micContext = new (window.AudioContext || window.webkitAudioContext)();
    micAnalyser = micContext.createAnalyser();
    micAnalyser.fftSize = 256;
    micSource = micContext.createMediaStreamSource(stream);
    micSource.connect(micAnalyser);
    const len = micAnalyser.frequencyBinCount, data = new Uint8Array(len);
    const poll = () => {
      if (!micAnalyser) return;
      micAnalyser.getByteFrequencyData(data);
      let s = 0;
      for (let i = 0; i < len; i++) s += data[i];
      audioVolumeTracker.mic = s / len;
      micRafId = requestAnimationFrame(poll);
    };
    poll();
  } catch (_) {}
}

function stopTrackingMicVolume() {
  if (micRafId) cancelAnimationFrame(micRafId);
  if (micSource) try { micSource.disconnect(); } catch (_) {}
  if (micContext && micContext.state !== "closed") try { micContext.close(); } catch (_) {}
  micContext = micAnalyser = micSource = null;
  audioVolumeTracker.mic = 0;
}

export async function createMicStream(onChunk, options = {}) {
  const rawStream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, sampleRate: 48000 },
  });
  let activeStream = rawStream, pipeline = null;
  try {
    const { AudioPipeline } = await import("../audio/AudioPipeline.js");
    pipeline = new AudioPipeline(options);
    const dest = await pipeline.init(rawStream);
    activeStream = dest.stream;
  } catch (_) {}
  const recorder = new MediaRecorder(activeStream, { mimeType: "audio/webm;codecs=opus" });
  recorder.ondataavailable = (e) => { if (e.data.size > 0) e.data.arrayBuffer().then(onChunk); };
  recorder.start(100);
  trackMicVolume(activeStream);
  return { recorder, stream: activeStream, rawStream, pipeline };
}

export function stopMicStream(micState) {
  if (!micState) return;
  const { recorder, rawStream, stream, pipeline } = micState;
  if (recorder && recorder.state !== "inactive") try { recorder.stop(); } catch (_) {}
  if (pipeline) try { pipeline.stop(); } catch (_) {}
  (rawStream || stream)?.getTracks().forEach((t) => { try { t.stop(); } catch (_) {} });
  stopTrackingMicVolume();
}

let speakerAnalyser = null, speakerRafId = null;

export function playAudioBuffer(arrayBuffer, audioContext) {
  const resume = audioContext.state === "suspended"
    ? Promise.race([audioContext.resume(), new Promise((_, r) => setTimeout(() => r(new Error("resume timeout")), 5000))])
    : Promise.resolve();
  return Promise.race([
    resume.then(() => audioContext.decodeAudioData(arrayBuffer.slice(0))).then((decoded) => {
      const src = audioContext.createBufferSource();
      src.buffer = decoded;
      if (!speakerAnalyser) { speakerAnalyser = audioContext.createAnalyser(); speakerAnalyser.fftSize = 256; }
      src.connect(speakerAnalyser);
      speakerAnalyser.connect(audioContext.destination);
      src.start(0);
      const len = speakerAnalyser.frequencyBinCount, data = new Uint8Array(len);
      const poll = () => {
        if (!speakerAnalyser) return;
        speakerAnalyser.getByteFrequencyData(data);
        let s = 0;
        for (let i = 0; i < len; i++) s += data[i];
        audioVolumeTracker.speaker = s / len;
        speakerRafId = requestAnimationFrame(poll);
      };
      if (!speakerRafId) poll();
      src.addEventListener("ended", () => {
        audioVolumeTracker.speaker = 0;
        if (speakerRafId) { cancelAnimationFrame(speakerRafId); speakerRafId = null; }
      });
      return src;
    }),
    new Promise((_, r) => setTimeout(() => r(new Error("playAudioBuffer timeout")), 10000))
  ]);
}
