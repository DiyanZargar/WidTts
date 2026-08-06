import { useRef, useContext, useCallback, useEffect, useState } from "react";
import { ConversationContext } from "../context/ConversationContext";
import { createConversationSocket } from "../services/websocketService";
import { useDeepgramAudio } from "./useDeepgramAudio";
import { useVAD } from "./useVAD";
import { audioVolumeTracker, setTTSPlaying } from "../utils/audioUtils";

// Legacy VAD polling: interrupt TTS when mic volume sustained above threshold
// Mic must exceed speaker volume by this margin to trigger (filters out echo bleed)
const INTERRUPT_VOLUME_THRESHOLD = 50;
const INTERRUPT_ABOVE_SPEAKER_MARGIN = 20;
const INTERRUPT_SUSTAINED_MS = 500;

export function useWebSocket(conversationType) {
  const { state, dispatch } = useContext(ConversationContext);
  const connRef = useRef(null);
  const streamingPlayerRef = useRef(null);
  const vadStopRef = useRef(null);
  const vadSetTTSRef = useRef(null);
  const { startMic, stopMic, playTTS, stopTTS, startStreamingTTS } = useDeepgramAudio();

  // ── Hybrid VAD integration (Silero V5 ONNX via @ricky0123/vad-web) ──
  const onVADInterruption = useCallback(({ probability }) => {
    console.log(
      `[PIPELINE] ${new Date().toISOString()} FE_VAD_INTERRUPT | prob=${probability.toFixed(3)}`
    );
    stopTTS();
    setTTSPlaying(false);
    dispatch({ type: "SET_ASSISTANT_HIGHLIGHT", value: false });
    connRef.current?.sendJson({ type: "tts_interrupt" });
  }, [stopTTS, dispatch]);

  const { start: startVAD, stop: stopVAD, setTTSPlaying: vadSetTTS } = useVAD({
    onInterruption: onVADInterruption,
  });
  // Store VAD refs for connect/disconnect
  useEffect(() => {
    vadStopRef.current = stopVAD;
    vadSetTTSRef.current = vadSetTTS;
  }, [stopVAD, vadSetTTS]);

  // Legacy volume polling: acts as safety-net fallback while VAD initializes
  useEffect(() => {
    let aboveThresholdSince = null;
    let pollId = null;

    const poll = () => {
      if (!audioVolumeTracker.isTTSPlaying) {
        aboveThresholdSince = null;
        return;
      }

      const micVol = audioVolumeTracker.mic;
      const speakerVol = audioVolumeTracker.speaker;
      // Only interrupt if mic volume exceeds BOTH the absolute threshold
      // AND is significantly above the speaker volume (ruling out echo bleed)
      const isAboveThreshold = micVol > INTERRUPT_VOLUME_THRESHOLD
        && micVol > speakerVol + INTERRUPT_ABOVE_SPEAKER_MARGIN;
      if (isAboveThreshold) {
        if (!aboveThresholdSince) {
          aboveThresholdSince = Date.now();
        } else if (Date.now() - aboveThresholdSince >= INTERRUPT_SUSTAINED_MS) {
          console.log(`[PIPELINE] ${new Date().toISOString()} FE_VOLUME_POLL_INTERRUPT | micVol=${micVol} speakerVol=${speakerVol} sustained_ms=${INTERRUPT_SUSTAINED_MS}`);
          aboveThresholdSince = null;
          stopTTS();
          setTTSPlaying(false);
          dispatch({ type: "SET_ASSISTANT_HIGHLIGHT", value: false });
          connRef.current?.sendJson({ type: "tts_interrupt" });
        }
      } else {
        aboveThresholdSince = null;
      }
    };

    pollId = setInterval(poll, 100);
    return () => clearInterval(pollId);
  }, [stopTTS, dispatch]);

  const connect = useCallback(() => {
    if (connRef.current) return;

    const savedSessionId = sessionStorage.getItem("widget_session_id");

    const onEvent = (evt) => {
      console.log(`[PIPELINE] ${new Date().toISOString()} FE_EVENT | type=${evt.event}`);
      switch (evt.event) {
        case "session_started":
          sessionStorage.setItem("widget_session_id", evt.payload.session_id);
          dispatch({ type: "SESSION_STARTED", sessionId: evt.payload.session_id });
          break;
        case "transcript_recovery":
          dispatch({ type: "RECOVER_TRANSCRIPT", messages: evt.payload.messages });
          break;
        case "user_partial_transcript":
          dispatch({ type: "SET_PARTIAL_TRANSCRIPT", text: evt.payload.text });
          break;
        case "user_transcript":
          dispatch({
            type: "APPEND_TRANSCRIPT_LINE",
            line: { id: Date.now(), speaker: "user", text: evt.payload.text, isHighlighted: false },
          });
          dispatch({ type: "CLEAR_PARTIAL_TRANSCRIPT" });
          break;
        case "question":
        case "instruction":
          dispatch({ type: "CLEAR_PARTIAL_TRANSCRIPT" });
          break;
        case "tts_audio_meta": {
          dispatch({
            type: "APPEND_TRANSCRIPT_LINE",
            line: { id: Date.now(), speaker: "assistant", text: evt.payload.text, isHighlighted: true },
          });
          dispatch({ type: "SET_ASSISTANT_HIGHLIGHT", value: true });

          if (evt.payload.is_streaming) {
            // Set TTS playing IMMEDIATELY — before async player creation
            // This ensures onAudio routes chunks to the streaming player, not the fallback
            setTTSPlaying(true);
            vadSetTTSRef.current?.(true);
            console.log(`[PIPELINE] ${new Date().toISOString()} FE_TTS_STREAM_START | text='${evt.payload.text}'`);
            // Reuse existing player if it's still active — don't kill mid-playback
            if (!streamingPlayerRef.current) {
              (async () => {
                try {
                  const player = await startStreamingTTS();
                  streamingPlayerRef.current = player;
                } catch (err) {
                  console.warn("[PIPELINE] FE_TTS_STREAM_START_ERROR |", err);
                  setTTSPlaying(false);
                  vadSetTTSRef.current?.(false);
                }
              })();
            }
          }
          break;
        }
        case "tts_stream_end": {
          const player = streamingPlayerRef.current;
          if (player) {
            player.onEnded(() => {
              const wasVadInterrupted = !audioVolumeTracker.isTTSPlaying;
              setTTSPlaying(false);
              vadSetTTSRef.current?.(false);
              dispatch({ type: "SET_ASSISTANT_HIGHLIGHT", value: false });
              // Release the old player so the next tts_audio_meta creates a fresh one
              streamingPlayerRef.current = null;
              if (!wasVadInterrupted) {
                connRef.current?.sendJson({ type: "tts_end" });
                console.log(`[PIPELINE] ${new Date().toISOString()} FE_TTS_END_SENT`);
              }
            });
            player.endStream();
          } else {
            setTTSPlaying(false);
            vadSetTTSRef.current?.(false);
            dispatch({ type: "SET_ASSISTANT_HIGHLIGHT", value: false });
            streamingPlayerRef.current = null;
            connRef.current?.sendJson({ type: "tts_end" });
          }
          break;
        }
        case "tts_stop":
          break;
        case "session_completed":
          stopMic();
          sessionStorage.removeItem("widget_session_id");
          dispatch({ type: "SESSION_COMPLETED" });
          break;
        case "session_cancelled":
          stopMic();
          sessionStorage.removeItem("widget_session_id");
          dispatch({ type: "SESSION_CANCELLED" });
          break;
        case "session_reset":
          dispatch({ type: "CLEAR_PARTIAL_TRANSCRIPT" });
          dispatch({ type: "SESSION_RESET" });
          break;
        default:
          break;
      }
    };

    const onAudio = (arrayBuffer) => {
      const player = streamingPlayerRef.current;
      if (player) {
        // Streaming player exists — send chunk directly to its queue/pending buffer
        player.appendChunk(new Uint8Array(arrayBuffer));
      } else if (audioVolumeTracker.isTTSPlaying) {
        // Fallback: non-streaming playback (single buffer)
        (async () => {
          try {
            await playTTS(arrayBuffer);
          } catch (err) {
            console.warn("[PIPELINE] FE_TTS_PLAYBACK_ERROR |", err.message || err);
          }
        })();
      } else {
        // Player not ready yet — buffer the chunk by creating the player
        // This handles the race condition where audio arrives before tts_audio_meta
        console.warn("[PIPELINE] FE_AUDIO_BEFORE_META — buffering chunk");
        setTTSPlaying(true);
        vadSetTTSRef.current?.(true);
        (async () => {
          try {
            const player = await startStreamingTTS();
            streamingPlayerRef.current = player;
            player.appendChunk(new Uint8Array(arrayBuffer));
          } catch (err) {
            console.warn("[PIPELINE] FE_EMERGENCY_PLAYER_ERROR |", err);
          }
        })();
      }
    };

    connRef.current = createConversationSocket({
      conversationType,
      sessionId: savedSessionId,
      onEvent,
      onAudio,
    });

    // Start microphone
    startMic((chunk) => {
      connRef.current?.sendAudioChunk(chunk);
    }).then((micState) => {
      if (micState?.stream) {
        setMicStream(micState.stream);
        // Start hybrid VAD on same MediaStream (runs parallel to MediaRecorder)
        startVAD(micState.stream).catch((e) => {
          console.warn("[useWebSocket] VAD start failed:", e.message);
        });
      }
    });
  }, [conversationType, dispatch, playTTS, startMic, stopMic, stopTTS, startStreamingTTS, startVAD]);

  const [micStream, setMicStream] = useState(null);
  const [muted, setMutedState] = useState(false);

  const setMuted = useCallback((isMuted) => {
    setMutedState(isMuted);
    if (micStream) {
      micStream.getAudioTracks().forEach((track) => {
        track.enabled = !isMuted;
      });
    }
  }, [micStream]);

  // Inside connect, save micState.stream to micStream
  // (We'll update connect below)
  
  const disconnect = useCallback(() => {
    setMicStream(null);
    setMutedState(false);
    stopMic();
    stopTTS();
    setTTSPlaying(false);
    streamingPlayerRef.current = null;
    vadStopRef.current?.();
    if (connRef.current) {
      connRef.current.close();
      connRef.current = null;
    }
  }, [stopMic, stopTTS]);

  return { connect, disconnect, micStream, muted, setMuted };
}
