/**
 * useLiveKitRoom — Custom hook wrapping livekit-client Room API.
 *
 * Uses livekit-client directly (NO LiveKit React components).
 * Exposes { connect, disconnect, toggleMute, sendData, audioLevel, listenLevel } for useVoiceSession.
 *
 * Audio level tracking: Creates Web Audio AnalyserNodes on both the local mic
 * track and the remote agent audio track. A RAF loop computes RMS levels at
 * ~15fps and exposes them via getAudioLevel() (agent TTS) and getListenLevel()
 * (user mic). These drive the Orb's visual reactivity.
 */

import { useRef, useCallback, useState } from 'react';
import { Room, RoomEvent, Track } from 'livekit-client';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export function useLiveKitRoom() {
  const roomRef = useRef(null);
  const audioElementRef = useRef(null);
  const [muted, setMuted] = useState(false);
  const localTrackRef = useRef(null);
  const callbacksRef = useRef({});

  // Audio level state — driven by RAF loop
  const [audioLevel, setAudioLevel] = useState(0);
  const [listenLevel, setListenLevel] = useState(0);

  // Web Audio refs
  const audioCtxRef = useRef(null);
  const localAnalyserRef = useRef(null);
  const remoteAnalyserRef = useRef(null);
  const rafRef = useRef(null);

  /**
   * Start a RAF loop that reads AnalyserNodes and updates audio levels.
   * Runs at ~15fps (every ~66ms) to avoid excessive re-renders.
   */
  const startLevelLoop = useCallback(() => {
    if (rafRef.current) return;

    let lastUpdate = 0;
    const INTERVAL = 66; // ~15fps

    const tick = (now) => {
      rafRef.current = requestAnimationFrame(tick);
      if (now - lastUpdate < INTERVAL) return;
      lastUpdate = now;

      // Local mic level
      if (localAnalyserRef.current) {
        const buf = new Uint8Array(localAnalyserRef.current.fftSize);
        localAnalyserRef.current.getByteTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) {
          const v = (buf[i] - 128) / 128;
          sum += v * v;
        }
        setListenLevel(Math.sqrt(sum / buf.length));
      } else {
        setListenLevel(0);
      }

      // Remote agent audio level
      if (remoteAnalyserRef.current) {
        const buf = new Uint8Array(remoteAnalyserRef.current.fftSize);
        remoteAnalyserRef.current.getByteTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) {
          const v = (buf[i] - 128) / 128;
          sum += v * v;
        }
        setAudioLevel(Math.sqrt(sum / buf.length));
      } else {
        setAudioLevel(0);
      }
    };

    rafRef.current = requestAnimationFrame(tick);
  }, []);

  /** Stop the RAF level loop and reset levels to 0. */
  const stopLevelLoop = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    setAudioLevel(0);
    setListenLevel(0);
  }, []);

  /** Tear down Web Audio resources. */
  const cleanupAudio = useCallback(() => {
    stopLevelLoop();
    localAnalyserRef.current = null;
    remoteAnalyserRef.current = null;
    if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
      audioCtxRef.current.close().catch(() => {});
    }
    audioCtxRef.current = null;
  }, [stopLevelLoop]);

  /**
   * Create a Web Audio AnalyserNode from a MediaStreamTrack.
   * Returns the AnalyserNode, or null if AudioContext is unavailable.
   */
  const createAnalyser = useCallback((mediaStreamTrack) => {
    try {
      if (!audioCtxRef.current || audioCtxRef.current.state === 'closed') {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        audioCtxRef.current = new AudioCtx();
      }
      const ctx = audioCtxRef.current;
      if (ctx.state === 'suspended') ctx.resume();

      const stream = new MediaStream([mediaStreamTrack]);
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      // Don't connect to destination — analysis only, no playback duplication
      return analyser;
    } catch (e) {
      console.warn('[LiveKit] Failed to create AnalyserNode:', e);
      return null;
    }
  }, []);

  const connect = useCallback(async (onEvent, onStatusChange) => {
    callbacksRef.current = { onEvent, onStatusChange };

    try {
      // Fetch token from backend
      const res = await fetch(`${API_BASE}/realtime/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversation_type: 'active_bot' }),
      });

      if (!res.ok) {
        const err = await res.json();
        onEvent?.({ event: 'error', payload: { message: err.detail || 'Connection failed' } });
        return;
      }

      const { token, room_name, server_url, session_id, bot_name } = await res.json();

      // Store session ID
      sessionStorage.setItem('widget_session_id', session_id);

      // Create and connect room
      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
        audioCaptureDefaults: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      roomRef.current = room;

      // Room events
      room.on(RoomEvent.Connected, () => {
        onStatusChange?.('connected');
      });

      room.on(RoomEvent.Disconnected, () => {
        onStatusChange?.('disconnected');
        onEvent?.({ event: 'session_completed', payload: {} });
      });

      // Track subscription (remote audio from TTS)
      room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
        if (track.kind === Track.Kind.Audio) {
          // Attach to hidden audio element for playback
          if (!audioElementRef.current) {
            const audio = document.createElement('audio');
            audio.autoplay = true;
            audio.style.display = 'none';
            document.body.appendChild(audio);
            audioElementRef.current = audio;
          }
          track.attach(audioElementRef.current);

          // Create AnalyserNode on the remote audio track for level visualization
          try {
            const mediaStreamTrack = track.mediaStreamTrack;
            if (mediaStreamTrack) {
              remoteAnalyserRef.current = createAnalyser(mediaStreamTrack);
              startLevelLoop();
            }
          } catch (e) {
            console.warn('[LiveKit] Failed to attach remote audio analyser:', e);
          }
        }
      });

      room.on(RoomEvent.TrackUnsubscribed, (track) => {
        track.detach();
        if (track.kind === Track.Kind.Audio) {
          remoteAnalyserRef.current = null;
        }
      });

      // Transcription events — LiveKit's native transcription pipeline.
      // Agent and user transcripts arrive here automatically from the
      // LiveKit agents framework (STT/TTS). This is the SOLE source of
      // transcript data for the frontend.
      room.on(RoomEvent.TranscriptionReceived, (segments, participant) => {
        if (!segments || segments.length === 0) return;

        for (const seg of segments) {
          const isLocal = participant?.identity === room.localParticipant?.identity;
          const text = seg.text?.trim();
          if (!text) continue;

          if (isLocal) {
            // User speech from STT
            if (seg.final) {
              onEvent?.({ event: 'user_transcript', payload: { text } });
            } else {
              onEvent?.({ event: 'user_partial_transcript', payload: { text } });
            }
          } else {
            // Agent speech from TTS
            if (seg.final) {
              onEvent?.({ event: 'tts_audio_meta', payload: { text, is_streaming: false } });
              onEvent?.({ event: 'tts_stream_end', payload: {} });
            } else {
              onEvent?.({ event: 'tts_audio_meta', payload: { text, is_streaming: true } });
            }
          }
        }
      });

      // Data channel — widTTS business events ONLY.
      // Transcripts are NOT sent here (they come via TranscriptionReceived above).
      // Reserved for: session lifecycle, conversation state, validation results,
      // thinking status, runtime events, analytics.
      room.on(RoomEvent.DataReceived, (payload, participant, kind, topic) => {
        try {
          const msg = JSON.parse(new TextDecoder().decode(payload));
          onEvent?.(msg);
        } catch (e) {
          // Binary data — ignore
        }
      });

      // Connect to room
      await room.connect(server_url, token);

      // Publish mic
      await room.localParticipant.setMicrophoneEnabled(true);
      localTrackRef.current = room.localParticipant.getTrackPublication(Track.Source.Microphone);

      // Create AnalyserNode on the local mic track for level visualization
      if (localTrackRef.current?.track?.mediaStreamTrack) {
        localAnalyserRef.current = createAnalyser(localTrackRef.current.track.mediaStreamTrack);
        startLevelLoop();
      }

      // Notify session started
      onEvent?.({
        event: 'session_started',
        payload: { session_id, bot_name, is_recovery: false },
      });

    } catch (err) {
      console.error('[LiveKit] Connection error:', err);
      onEvent?.({ event: 'error', payload: { message: err.message } });
    }
  }, [createAnalyser, startLevelLoop]);

  const disconnect = useCallback(() => {
    cleanupAudio();

    if (roomRef.current) {
      roomRef.current.disconnect();
      roomRef.current = null;
    }
    if (audioElementRef.current) {
      audioElementRef.current.remove();
      audioElementRef.current = null;
    }
    localTrackRef.current = null;
    sessionStorage.removeItem('widget_session_id');
  }, [cleanupAudio]);

  const toggleMute = useCallback((muted) => {
    setMuted(muted);
    if (roomRef.current) {
      roomRef.current.localParticipant.setMicrophoneEnabled(!muted);
    }
    // Zero out listen level immediately when muted
    if (muted) {
      setListenLevel(0);
      localAnalyserRef.current = null;
    } else if (localTrackRef.current?.track?.mediaStreamTrack) {
      localAnalyserRef.current = createAnalyser(localTrackRef.current.track.mediaStreamTrack);
    }
  }, [createAnalyser]);

  const sendData = useCallback((data) => {
    if (roomRef.current && roomRef.current.state === 'connected') {
      const encoded = new TextEncoder().encode(JSON.stringify(data));
      roomRef.current.localParticipant.publishData(encoded, { reliable: true });
    }
  }, []);

  return {
    connect,
    disconnect,
    toggleMute,
    sendData,
    micStream: null, // legacy compat — LiveKit owns the mic
    muted,
    setMuted: toggleMute,
    // Audio level getters for Orb visual reactivity
    audioLevel,   // 0-1 RMS of remote agent TTS audio
    listenLevel,  // 0-1 RMS of local user mic input
  };
}
