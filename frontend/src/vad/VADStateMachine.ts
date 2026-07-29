// VADStateMachine.ts — Hybrid VAD state machine
//
// States: IDLE → SPEECH_START_CANDIDATE → SPEECH_CONFIRMED → SPEECH_ONGOING
//         → SPEECH_END_CANDIDATE → COOLDOWN → IDLE
//
// Uses dual-engine fusion: WebRTC for fast start detection, Silero for
// high-confidence confirmation and end detection.

import { AdaptiveThreshold } from "./AdaptiveThreshold";

export enum VADState {
  IDLE = "IDLE",
  SPEECH_START_CANDIDATE = "SPEECH_START_CANDIDATE",
  SPEECH_CONFIRMED = "SPEECH_CONFIRMED",
  SPEECH_ONGOING = "SPEECH_ONGOING",
  SPEECH_END_CANDIDATE = "SPEECH_END_CANDIDATE",
  COOLDOWN = "COOLDOWN",
}

export interface VADConfig {
  minSpeechDurationMs: number; // Minimum speech segment (default 250ms)
  minSilenceDurationMs: number; // Silence before end detection (default 300ms)
  speechStartTimeoutMs: number; // Max wait for Silero confirmation (default 150ms)
  cooldownMs: number; // Post-speech cooldown (default 50ms)
}

const DEFAULT_CONFIG: VADConfig = {
  minSpeechDurationMs: 250,
  minSilenceDurationMs: 300,
  speechStartTimeoutMs: 150,
  cooldownMs: 50,
};

export class VADStateMachine {
  private _state = VADState.IDLE;
  private _adaptiveThreshold = new AdaptiveThreshold();
  private _config: VADConfig;
  private _speechStartTimestamp = 0;
  private _silenceStartTimestamp = 0;
  private _candidateTimestamp = 0;
  private _frameCount = 0;
  private _speechFrameCount = 0;

  // Callbacks
  public onSpeechStart: (() => void) | null = null;
  public onSpeechEnd: (() => void) | null = null;
  public onInterruption: (() => void) | null = null;
  public onStateChange: ((state: VADState) => void) | null = null;

  constructor(config: Partial<VADConfig> = {}) {
    this._config = { ...DEFAULT_CONFIG, ...config };
  }

  /** Process one frame: WebRTC boolean + Silero probability → state transition */
  process(
    webrtcSpeech: boolean,
    sileroProbability: number,
    ttsPlaying: boolean,
    timestamp: number
  ): void {
    this._frameCount++;
    const now = timestamp;

    // Update adaptive thresholds with Silero probability during non-speech
    const isCurrentlySpeech =
      this._state === VADState.SPEECH_CONFIRMED ||
      this._state === VADState.SPEECH_ONGOING;
    this._adaptiveThreshold.update(sileroProbability, isCurrentlySpeech);

    const startThreshold = this._adaptiveThreshold.startThreshold;
    const continueThreshold = this._adaptiveThreshold.continueThreshold;

    switch (this._state) {
      case VADState.IDLE:
        if (webrtcSpeech) {
          this._transition(VADState.SPEECH_START_CANDIDATE, now);
          this._candidateTimestamp = now;
        }
        break;

      case VADState.SPEECH_START_CANDIDATE:
        if (sileroProbability >= startThreshold) {
          // Silero confirms — speech has started
          this._transition(VADState.SPEECH_CONFIRMED, now);
          this._speechStartTimestamp = now;
          this._speechFrameCount = 0;

          // Emit speech start or interruption
          if (ttsPlaying && this.onInterruption) {
            this.onInterruption();
          } else if (this.onSpeechStart) {
            this.onSpeechStart();
          }
        } else if (now - this._candidateTimestamp > this._config.speechStartTimeoutMs) {
          // Silero didn't confirm in time — false positive, go back to IDLE
          this._transition(VADState.IDLE, now);
        } else if (!webrtcSpeech && sileroProbability < 0.3) {
          // Both engines say silence — false positive
          this._transition(VADState.IDLE, now);
        }
        break;

      case VADState.SPEECH_CONFIRMED:
        this._speechFrameCount++;
        // Stay in SPEECH_CONFIRMED until minSpeechDuration passes
        if (now - this._speechStartTimestamp >= this._config.minSpeechDurationMs) {
          this._transition(VADState.SPEECH_ONGOING, now);
        }
        break;

      case VADState.SPEECH_ONGOING:
        this._speechFrameCount++;
        if (
          !webrtcSpeech &&
          sileroProbability < continueThreshold
        ) {
          this._transition(VADState.SPEECH_END_CANDIDATE, now);
          this._silenceStartTimestamp = now;
        }
        break;

      case VADState.SPEECH_END_CANDIDATE:
        if (
          webrtcSpeech ||
          sileroProbability >= startThreshold
        ) {
          // Speech resumed — go back
          this._transition(VADState.SPEECH_ONGOING, now);
        } else if (
          now - this._silenceStartTimestamp >= this._config.minSilenceDurationMs
        ) {
          // Silence sustained — speech has ended
          this._transition(VADState.COOLDOWN, now);
          if (this.onSpeechEnd) {
            this.onSpeechEnd();
          }
        }
        break;

      case VADState.COOLDOWN:
        if (now - this._silenceStartTimestamp - this._config.minSilenceDurationMs >= this._config.cooldownMs) {
          this._transition(VADState.IDLE, now);
        }
        break;
    }
  }

  private _transition(newState: VADState, timestamp: number): void {
    if (this._state === newState) return;
    this._state = newState;
    if (this.onStateChange) {
      this.onStateChange(newState);
    }
  }

  get state(): VADState {
    return this._state;
  }

  get startThreshold(): number {
    return this._adaptiveThreshold.startThreshold;
  }

  get continueThreshold(): number {
    return this._adaptiveThreshold.continueThreshold;
  }

  get noiseFloor(): number {
    return this._adaptiveThreshold.noiseFloor;
  }

  get speechDurationMs(): number {
    if (this._speechStartTimestamp === 0) return 0;
    return Date.now() - this._speechStartTimestamp;
  }

  reset(): void {
    this._state = VADState.IDLE;
    this._adaptiveThreshold.reset();
    this._speechStartTimestamp = 0;
    this._silenceStartTimestamp = 0;
    this._candidateTimestamp = 0;
    this._frameCount = 0;
    this._speechFrameCount = 0;
  }
}
