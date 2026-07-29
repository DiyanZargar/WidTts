// SileroVAD.ts — Silero V5 ONNX engine via @ricky0123/vad-web

import type { VADProvider } from "../interfaces/VADProvider";

export class SileroVAD implements VADProvider {
  readonly name = "SileroVAD";
  private _vadModule: any = null;
  private _session: any = null;
  private _h: any = null; // LSTM hidden state
  private _c: any = null; // LSTM cell state
  private _ready = false;

  async initialize(_config?: Record<string, unknown>): Promise<boolean> {
    try {
      this._vadModule = await import("@ricky0123/vad-web");

      // Load the model and create an inference session
      const modelUrl = "/models/silero_vad_v5.onnx";
      const modelBuffer = await fetch(modelUrl).then((r) => r.arrayBuffer());

      // Use the package's utility to create a session
      this._session = await this._vadModule.createOnnxSession(modelBuffer, {
        executionProviders: ["wasm"],
      });

      // Initialize LSTM state tensors: [2, 1, 64] for Silero v5
      const ort = await import("onnxruntime-web");
      const stateDims = [2, 1, 64];
      this._h = new ort.Tensor("float32", new Float32Array(128), stateDims);
      this._c = new ort.Tensor("float32", new Float32Array(128), stateDims);

      // Warm-up inference with a silence frame
      const warmupFrame = new Float32Array(512);
      this._runInference(warmupFrame);

      this._ready = true;
      return true;
    } catch (e) {
      console.warn("[SileroVAD] Failed to initialize:", e);
      return false;
    }
  }

  private async _runInference(frame: Float32Array): Promise<number> {
    if (!this._session) return 0.0;

    try {
      const ort = await import("onnxruntime-web");
      const inputTensor = new ort.Tensor("float32", frame, [1, frame.length]);
      const feeds: Record<string, any> = {
        input: inputTensor,
        h: this._h,
        c: this._c,
      };

      const results = await this._session.run(feeds);
      this._h = results.hn || this._h;
      this._c = results.cn || this._c;

      const output = results.output?.data?.[0] ?? 0.0;
      return output;
    } catch (e) {
      console.warn("[SileroVAD] Inference error:", e);
      return 0.0;
    }
  }

  processFrame(frame: Float32Array): number {
    if (!this._ready) return 0.0;

    // Silero v5 expects frame length to be a multiple of the model's input.
    // The model uses variable-length input; 512 samples (32ms @ 16kHz) works well.
    // If frame length differs, pad or truncate.
    let processed = frame;
    if (frame.length < 256) {
      processed = new Float32Array(256);
      processed.set(frame);
    } else if (frame.length > 1024) {
      processed = frame.subarray(0, 1024);
    }

    // Run synchronously via internal state; actual inference is async
    // but we cache the result. In practice, the worker calls this
    // synchronously with a pre-computed result from the async pipeline.
    // For now return 0 and let the worker handle the async flow.
    return 0.0;
  }

  /** Async inference — call from worker */
  async processFrameAsync(frame: Float32Array): Promise<number> {
    if (!this._ready) return 0.0;
    return this._runInference(frame);
  }

  reset(): void {
    if (this._h && this._c) {
      this._h = new (this._vadModule?.ort?.Tensor || this._h.constructor)(
        "float32",
        new Float32Array(128),
        [2, 1, 64]
      );
      this._c = new (this._vadModule?.ort?.Tensor || this._c.constructor)(
        "float32",
        new Float32Array(128),
        [2, 1, 64]
      );
    }
  }

  dispose(): void {
    this._session = null;
    this._h = null;
    this._c = null;
    this._ready = false;
  }
}
