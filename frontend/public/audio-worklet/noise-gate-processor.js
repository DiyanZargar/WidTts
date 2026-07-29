/**
 * Adaptive Noise Gate AudioWorklet
 * Continuously estimates noise floor and gates audio below threshold.
 * Prevents transmission of silence and low-energy environmental sounds.
 */
class NoiseGateProcessor extends AudioWorkletProcessor {
  static get parameterDescriptors() {
    return [
      { name: "attack", defaultValue: 0.01, minValue: 0.001, maxValue: 0.1, automationRate: "k-rate" },
      { name: "release", defaultValue: 0.1, minValue: 0.01, maxValue: 1.0, automationRate: "k-rate" },
      { name: "holdTime", defaultValue: 0.15, minValue: 0.01, maxValue: 1.0, automationRate: "k-rate" },
    ];
  }

  constructor() {
    super();
    this._noiseFloor = 0.001;
    this._gateOpen = false;
    this._holdSamples = 0;
    this._envelope = 0;
    this._gateMultiplier = 0;
    this._sampleRate = sampleRate;
    this._smoothingFactor = 0.999;
    this._gateThresholdMultiplier = 1.8;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    const output = outputs[0];
    if (!input || !input.length) return true;

    const attack = parameters.attack[0];
    const release = parameters.release[0];
    const holdTime = parameters.holdTime[0];
    const holdSamples = Math.floor(holdTime * this._sampleRate);

    const attackCoeff = Math.exp(-1.0 / (attack * this._sampleRate));
    const releaseCoeff = Math.exp(-1.0 / (release * this._sampleRate));

    const channelCount = input.length;
    const frameSize = input[0].length;

    for (let i = 0; i < frameSize; i++) {
      // RMS across channels
      let rms = 0;
      for (let ch = 0; ch < channelCount; ch++) {
        rms += input[ch][i] * input[ch][i];
      }
      rms = Math.sqrt(rms / channelCount);

      // Update noise floor (only when gate is closed)
      if (!this._gateOpen && this._holdSamples <= 0) {
        this._noiseFloor = this._noiseFloor * this._smoothingFactor + rms * (1 - this._smoothingFactor);
      }

      // Envelope follower
      const target = rms;
      const coeff = target > this._envelope ? attackCoeff : releaseCoeff;
      this._envelope = coeff * this._envelope + (1 - coeff) * target;

      // Gate decision
      const threshold = Math.max(this._noiseFloor * this._gateThresholdMultiplier, 0.001);
      if (this._envelope > threshold) {
        this._gateOpen = true;
        this._holdSamples = holdSamples;
      } else if (this._holdSamples > 0) {
        this._holdSamples--;
      } else {
        this._gateOpen = false;
      }

      // Smooth gate multiplier
      const targetMult = this._gateOpen ? 1.0 : 0.0;
      const smoothRate = this._gateOpen ? 0.1 : 0.02;
      this._gateMultiplier += (targetMult - this._gateMultiplier) * smoothRate;

      // Apply gate
      for (let ch = 0; ch < channelCount; ch++) {
        output[ch][i] = input[ch][i] * this._gateMultiplier;
      }
    }

    // Report state to main thread periodically
    this.port.postMessage({
      gateOpen: this._gateOpen,
      noiseFloor: this._noiseFloor,
      envelope: this._envelope,
    });

    return true;
  }
}

registerProcessor("noise-gate", NoiseGateProcessor);
