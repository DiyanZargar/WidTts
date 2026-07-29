// WebRTCVAD.ts — Fast energy-based VAD (pre-filter), extensible to WASM
//
// Uses RMS energy thresholding with zero-crossing rate as a fast pre-filter.
// Intended as a companion to SileroVAD for low-latency start detection.
// Architecture allows swap-in of genuine WebRTC WASM later.

import type { VADProvider } from "../interfaces/VADProvider";

const DEFAULT_ENERGY_THRESHOLD = 0.01; // RMS threshold for speech

export class WebRTCVAD implements VADProvider {
  readonly name = "WebRTCVAD";
  private _energyThreshold: number;

  constructor(energyThreshold = DEFAULT_ENERGY_THRESHOLD) {
    this._energyThreshold = energyThreshold;
  }

  async initialize(_config?: Record<string, unknown>): Promise<boolean> {
    return true; // No WASM needed for energy-based mode
  }

  processFrame(frame: Float32Array): number {
    // RMS energy
    let sumSquares = 0;
    for (let i = 0; i < frame.length; i++) {
      sumSquares += frame[i] * frame[i];
    }
    const rms = Math.sqrt(sumSquares / frame.length);

    // Zero-crossing rate (normalized)
    let zcr = 0;
    for (let i = 1; i < frame.length; i++) {
      if ((frame[i] >= 0) !== (frame[i - 1] >= 0)) {
        zcr++;
      }
    }
    const normalizedZCR = zcr / (frame.length - 1);

    // Speech detection: high energy AND reasonable ZCR
    // Music/tones have low ZCR; noise has high ZCR; speech is in between
    const isSpeech =
      rms > this._energyThreshold &&
      normalizedZCR > 0.05 &&
      normalizedZCR < 0.60;

    return isSpeech ? 1.0 : 0.0;
  }

  reset(): void {
    // Stateless
  }

  dispose(): void {
    // Nothing to dispose
  }
}
