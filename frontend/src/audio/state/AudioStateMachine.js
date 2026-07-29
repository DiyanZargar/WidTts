/**
 * Audio State Machine — independent from Conversation FSM.
 *
 * Tracks the audio pipeline lifecycle:
 *   Idle → Initializing → Listening → SpeechDetected → Streaming →
 *   Paused → Interrupted → Recovering → Closed
 */

const AudioState = {
  IDLE: "idle",
  INITIALIZING: "initializing",
  LISTENING: "listening",
  SPEECH_DETECTED: "speech_detected",
  STREAMING: "streaming",
  PAUSED: "paused",
  INTERRUPTED: "interrupted",
  RECOVERING: "recovering",
  CLOSED: "closed",
};

const TRANSITIONS = {
  [AudioState.IDLE]: [AudioState.INITIALIZING, AudioState.CLOSED],
  [AudioState.INITIALIZING]: [AudioState.LISTENING, AudioState.CLOSED],
  [AudioState.LISTENING]: [AudioState.SPEECH_DETECTED, AudioState.PAUSED, AudioState.INTERRUPTED, AudioState.CLOSED],
  [AudioState.SPEECH_DETECTED]: [AudioState.STREAMING, AudioState.LISTENING, AudioState.INTERRUPTED, AudioState.CLOSED],
  [AudioState.STREAMING]: [AudioState.LISTENING, AudioState.INTERRUPTED, AudioState.PAUSED, AudioState.CLOSED],
  [AudioState.PAUSED]: [AudioState.LISTENING, AudioState.RECOVERING, AudioState.CLOSED],
  [AudioState.INTERRUPTED]: [AudioState.RECOVERING, AudioState.LISTENING, AudioState.CLOSED],
  [AudioState.RECOVERING]: [AudioState.LISTENING, AudioState.INITIALIZING, AudioState.CLOSED],
  [AudioState.CLOSED]: [AudioState.IDLE],
};

export class AudioStateMachine {
  constructor() {
    this._state = AudioState.IDLE;
    this._history = [{ state: AudioState.IDLE, at: Date.now(), reason: "init" }];
    this._listeners = new Set();
  }

  get state() {
    return this._state;
  }

  get history() {
    return [...this._history];
  }

  transition(target, reason = "") {
    const allowed = TRANSITIONS[this._state];
    if (!allowed || !allowed.includes(target)) {
      console.warn(`[AUDIO_FSM] Illegal transition: ${this._state} → ${target} (${reason})`);
      return false;
    }
    const old = this._state;
    this._state = target;
    this._history.push({ state: target, at: Date.now(), reason });
    if (this._history.length > 50) this._history.shift();

    for (const listener of this._listeners) {
      try { listener({ old, target, reason }); } catch (_) {}
    }
    return true;
  }

  onChange(listener) {
    this._listeners.add(listener);
    return () => this._listeners.delete(listener);
  }

  snapshot() {
    return { state: this._state, historyLength: this._history.length };
  }
}

export { AudioState };
