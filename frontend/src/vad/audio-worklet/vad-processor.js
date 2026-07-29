// vad-processor.js — AudioWorklet for real-time PCM tap
//
// Runs on AudioWorklet thread. Captures raw PCM at 16kHz and sends
// 30ms frames to the Web Worker via postMessage with ArrayBuffer transfer.
// The original audio stream passes through unchanged to the output.

const TARGET_SAMPLE_RATE = 16000;
const FRAME_DURATION_MS = 30;
const FRAME_SIZE = Math.floor((TARGET_SAMPLE_RATE * FRAME_DURATION_MS) / 1000); // 480 samples

class VADAudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = new Float32Array(FRAME_SIZE);
    this._bufferIdx = 0;

    // Resampling state (linear interpolation)
    this._inputSampleRate = 0;
    this._resampleRatio = 1.0;
    this._resamplePos = 0.0;

    // Register message handler from main thread
    this.port.onmessage = (event) => {
      if (event.data.type === "config") {
        // Accept config updates (e.g., frame duration changes)
      }
    };
  }

  /**
   * Downmix multi-channel input to mono
   */
  _downmixToMono(inputs) {
    if (!inputs || !inputs[0]) return null;

    const channelCount = inputs.length;
    if (channelCount === 0) return null;

    const frameCount = inputs[0].length;
    if (frameCount === 0) return null;

    const mono = new Float32Array(frameCount);
    for (let i = 0; i < frameCount; i++) {
      let sum = 0;
      for (let ch = 0; ch < channelCount; ch++) {
        sum += (inputs[ch]?.[i] ?? 0);
      }
      mono[i] = sum / channelCount;
    }
    return mono;
  }

  process(inputs, outputs, _parameters) {
    const input = inputs[0];
    if (!input || !input[0]) {
      // Still pass through
      return true;
    }

    // Downmix to mono
    const mono = this._downmixToMono(inputs);
    if (!mono) return true;

    // Detect input sample rate on first call
    if (this._inputSampleRate === 0) {
      this._inputSampleRate = sampleRate; // global in AudioWorklet scope
      this._resampleRatio = TARGET_SAMPLE_RATE / this._inputSampleRate;
    }

    // Simple linear resampling to 16kHz
    for (let i = 0; i < mono.length; i++) {
      this._resamplePos += this._resampleRatio;
      while (this._resamplePos >= 1.0 && this._bufferIdx < FRAME_SIZE) {
        this._resamplePos -= 1.0;
        this._buffer[this._bufferIdx] = mono[i];
        this._bufferIdx++;

        // Frame complete — send to worker
        if (this._bufferIdx >= FRAME_SIZE) {
          const frame = new Float32Array(this._buffer);
          this.port.postMessage(
            { type: "frame", pcm: frame.buffer },
            [frame.buffer]
          );
          this._buffer = new Float32Array(FRAME_SIZE);
          this._bufferIdx = 0;
        }
      }
    }

    // Passthrough: copy input to output unchanged
    const output = outputs[0];
    if (output) {
      for (let ch = 0; ch < Math.min(inputs.length, output.length); ch++) {
        const src = inputs[ch];
        const dst = output[ch];
        if (src && dst) {
          dst.set(src.length <= dst.length ? src : src.subarray(0, dst.length));
        }
      }
    }

    return true; // Keep processor alive
  }
}

registerProcessor("vad-processor", VADAudioProcessor);
