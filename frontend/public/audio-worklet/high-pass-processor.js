/**
 * High-Pass Filter AudioWorklet
 * Removes low-frequency noise (AC hum, desk vibration, handling noise).
 * Configurable cutoff frequency (default 80Hz).
 */
class HighPassFilterProcessor extends AudioWorkletProcessor {
  static get parameterDescriptors() {
    return [
      { name: "cutoff", defaultValue: 80, minValue: 20, maxValue: 500, automationRate: "k-rate" },
    ];
  }

  constructor() {
    super();
    this._prevX = 0;
    this._prevY = 0;
    this._alpha = 0;
    this._lastCutoff = 0;
    this._sampleRate = sampleRate;
  }

  _updateCoefficients(cutoff) {
    if (cutoff === this._lastCutoff) return;
    this._lastCutoff = cutoff;
    const rc = 1.0 / (2.0 * Math.PI * cutoff);
    const dt = 1.0 / this._sampleRate;
    this._alpha = rc / (rc + dt);
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    const output = outputs[0];
    if (!input || !input.length) return true;

    const cutoff = parameters.cutoff[0];
    this._updateCoefficients(cutoff);

    for (let channel = 0; channel < input.length; channel++) {
      const inp = input[channel];
      const out = output[channel];
      let prevX = channel === 0 ? this._prevX : this._prevX2 || 0;
      let prevY = channel === 0 ? this._prevY : this._prevY2 || 0;

      for (let i = 0; i < inp.length; i++) {
        const x = inp[i];
        const y = this._alpha * (prevY + x - prevX);
        out[i] = y;
        prevX = x;
        prevY = y;
      }

      if (channel === 0) {
        this._prevX = prevX;
        this._prevY = prevY;
      } else {
        this._prevX2 = prevX;
        this._prevY2 = prevY;
      }
    }
    return true;
  }
}

registerProcessor("high-pass-filter", HighPassFilterProcessor);
