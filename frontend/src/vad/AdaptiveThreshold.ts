// AdaptiveThreshold.ts — Noise-floor adaptive VAD thresholds
//
// Dynamically adjusts speech detection thresholds based on ambient noise.
// In quiet rooms, thresholds stay low. In noisy environments, they rise.

export class AdaptiveThreshold {
  private _noiseFloor = 0.0;
  private _noiseAlpha = 0.95; // EMA smoothing factor
  private _baseStart = 0.75;
  private _baseContinue = 0.55;
  private _hysteresis = 0.15;

  /** Feed a probability value to update noise floor estimate */
  update(probability: number, isSpeech: boolean): void {
    if (!isSpeech) {
      // Update noise floor estimate during silence/non-speech
      this._noiseFloor =
        this._noiseAlpha * this._noiseFloor +
        (1 - this._noiseAlpha) * probability;
    }
  }

  /** Threshold for speech start detection */
  get startThreshold(): number {
    // Raise threshold in noisy environments
    return Math.min(0.95, this._baseStart + this._noiseFloor * 0.5);
  }

  /** Threshold for continued speech (lower due to hysteresis) */
  get continueThreshold(): number {
    return Math.max(0.30, this.startThreshold - this._hysteresis);
  }

  /** Current noise floor estimate */
  get noiseFloor(): number {
    return this._noiseFloor;
  }

  /** Reset noise floor */
  reset(): void {
    this._noiseFloor = 0.0;
  }
}
