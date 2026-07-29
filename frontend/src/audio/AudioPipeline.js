/**
 * Audio Preprocessing Pipeline
 *
 * Chains AudioWorklet processors for enterprise-grade audio preprocessing:
 *   Browser DSP → RNNoise → High-Pass Filter → Noise Gate → VAD
 *
 * Each module is independently replaceable. The pipeline runs entirely on the
 * client before audio is transmitted over WebSocket.
 */
export class AudioPipeline {
  constructor(options = {}) {
    this._audioContext = null;
    this._nodes = [];
    this._source = null;
    this._destination = null;
    this._active = false;

    // Configurable options with sane defaults
    this._options = {
      highPassCutoff: options.highPassCutoff ?? 80,
      noiseGateAttack: options.noiseGateAttack ?? 0.01,
      noiseGateRelease: options.noiseGateRelease ?? 0.1,
      noiseGateHold: options.noiseGateHold ?? 0.15,
      enableRNNoise: options.enableRNNoise ?? true,
      enableHighPass: options.enableHighPass ?? true,
      enableNoiseGate: options.enableNoiseGate ?? true,
    };
  }

  /**
   * Initialize the pipeline with a MediaStream source.
   * Returns the processed MediaStreamAudioDestinationNode.
   */
  async init(mediaStream) {
    if (this._active) return this._destination;

    this._audioContext = new AudioContext({ sampleRate: 48000 });
    if (this._audioContext.state === "suspended") {
      await this._audioContext.resume();
    }

    this._source = this._audioContext.createMediaStreamSource(mediaStream);
    this._destination = this._audioContext.createMediaStreamDestination();

    // Build the processing chain
    let currentNode = this._source;

    // 1. RNNoise AI Denoiser
    if (this._options.enableRNNoise) {
      const rnnoise = await this._createRNNoiseNode();
      if (rnnoise) {
        currentNode.connect(rnnoise);
        currentNode = rnnoise;
        this._nodes.push(rnnoise);
      }
    }

    // 2. High-Pass Filter
    if (this._options.enableHighPass) {
      const highPass = await this._createHighPassNode();
      if (highPass) {
        currentNode.connect(highPass);
        currentNode = highPass;
        this._nodes.push(highPass);
      }
    }

    // 3. Adaptive Noise Gate
    if (this._options.enableNoiseGate) {
      const noiseGate = await this._createNoiseGateNode();
      if (noiseGate) {
        currentNode.connect(noiseGate);
        currentNode = noiseGate;
        this._nodes.push(noiseGate);
      }
    }

    // Connect final node to destination
    currentNode.connect(this._destination);
    this._active = true;

    console.log(
      `[AUDIO_PIPELINE] Initialized with ${this._nodes.length} processors: ` +
      [
        this._options.enableRNNoise && "RNNoise",
        this._options.enableHighPass && "HighPass",
        this._options.enableNoiseGate && "NoiseGate",
      ].filter(Boolean).join(", ")
    );

    return this._destination;
  }

  async _createRNNoiseNode() {
    try {
      await this._audioContext.audioWorklet.addModule("/audio-worklet/rnnoise-processor.js");
      const node = new AudioWorkletNode(this._audioContext, "rnnoise-processor");
      return node;
    } catch (e) {
      console.warn("[AUDIO_PIPELINE] RNNoise worklet load failed:", e.message);
      return null;
    }
  }

  async _createHighPassNode() {
    try {
      await this._audioContext.audioWorklet.addModule("/audio-worklet/high-pass-processor.js");
      const node = new AudioWorkletNode(this._audioContext, "high-pass-filter", {
        parameterData: { cutoff: this._options.highPassCutoff },
      });
      return node;
    } catch (e) {
      console.warn("[AUDIO_PIPELINE] HighPass worklet load failed:", e.message);
      return null;
    }
  }

  async _createNoiseGateNode() {
    try {
      await this._audioContext.audioWorklet.addModule("/audio-worklet/noise-gate-processor.js");
      const node = new AudioWorkletNode(this._audioContext, "noise-gate", {
        parameterData: {
          attack: this._options.noiseGateAttack,
          release: this._options.noiseGateRelease,
          holdTime: this._options.noiseGateHold,
        },
      });
      // Listen for gate state changes from the worklet
      node.port.onmessage = (e) => {
        if (e.data.gateOpen !== undefined) {
          this._gateOpen = e.data.gateOpen;
          this._noiseFloor = e.data.noiseFloor;
        }
      };
      return node;
    } catch (e) {
      console.warn("[AUDIO_PIPELINE] NoiseGate worklet load failed:", e.message);
      return null;
    }
  }

  get isActive() {
    return this._active;
  }

  get gateOpen() {
    return this._gateOpen ?? false;
  }

  get noiseFloor() {
    return this._noiseFloor ?? 0;
  }

  /**
   * Get the processed MediaStream for downstream consumers (VAD, MediaRecorder).
   */
  get outputStream() {
    return this._destination?.stream ?? null;
  }

  /**
   * Tear down the pipeline and disconnect all nodes.
   */
  stop() {
    this._active = false;
    this._gateOpen = false;
    for (const node of this._nodes) {
      try { node.disconnect(); } catch (_) {}
    }
    this._nodes = [];
    if (this._source) {
      try { this._source.disconnect(); } catch (_) {}
      this._source = null;
    }
    if (this._audioContext && this._audioContext.state !== "closed") {
      this._audioContext.close().catch(() => {});
    }
    this._audioContext = null;
    this._destination = null;
    console.log("[AUDIO_PIPELINE] Stopped");
  }
}
