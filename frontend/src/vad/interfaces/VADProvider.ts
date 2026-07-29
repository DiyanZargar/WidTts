// VADProvider.ts — Common interface for all VAD engines

export interface VADProvider {
  /** Unique provider name */
  readonly name: string;

  /** Initialize the engine. Returns true if ready. */
  initialize(config?: Record<string, unknown>): Promise<boolean>;

  /** Run inference on a single 30ms frame of 16kHz mono Float32 PCM.
   *  Returns probability in [0.0, 1.0]. */
  processFrame(frame: Float32Array): number;

  /** Reset any internal state. */
  reset(): void;

  /** Release resources. */
  dispose(): void;
}
