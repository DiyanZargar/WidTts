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

  const connect = useCallback(async (onEvent, onStatusChange, botSlug) => {
    callbacksRef.current = { onEvent, onStatusChange };

    // Guard: cleanly disconnect any prior active room/audio before connecting
    if (roomRef.current) {
      try {
        roomRef.current.disconnect();
      } catch (_) {}
      roomRef.current = null;
    }
    if (audioElementRef.current) {
      audioElementRef.current.remove();
      audioElementRef.current = null;
    }
    cleanupAudio();

    try {
      // Fetch token from backend — bot-specific or active bot
      const tokenUrl = botSlug
        ? `${API_BASE}/api/bot/${botSlug}/token`
        : `${API_BASE}/realtime/token`;
      const tokenBody = botSlug
        ? JSON.stringify({ conversation_type: 'bot_session' })
        : JSON.stringify({ conversation_type: 'active_bot' });

      const res = await fetch(tokenUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: tokenBody,
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

      // Track subscription (remote audio from TTS)
      room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
        if (track.kind === Track.Kind.Audio) {
          // Remove any pre-existing audio element before attaching a new one
          if (audioElementRef.current) {
            audioElementRef.current.remove();
            audioElementRef.current = null;
          }

          // Attach using LiveKit's managed element generator for zero-latency WebRTC audio
          const audioEl = track.attach();
          audioEl.id = `livekit-audio-${participant.identity || 'agent'}`;
          audioEl.style.display = 'none';
          document.body.appendChild(audioEl);
          audioElementRef.current = audioEl;

          // Explicitly invoke play() to bypass browser autoplay restrictions
          audioEl.play().catch((err) => {
            console.warn('[LiveKit] Autoplay prevented, user interaction required:', err);
          });

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
          if (audioElementRef.current) {
            audioElementRef.current.remove();
            audioElementRef.current = null;
          }
          remoteAnalyserRef.current = null;
        }
      });

      // Text Stream Transcription Handler — LiveKit 2.x Agent Protocol ('lk.transcription')
      room.registerTextStreamHandler('lk.transcription', async (reader, participantInfo) => {
        const info = reader.info || {};
        const attrs = info.attributes || {};
        const localIdentity = room.localParticipant?.identity;
        const localMicSid = room.localParticipant?.getTrackPublication(Track.Source.Microphone)?.trackSid;

        // Determine speaker identity: user STT vs agent TTS
        const publishOnBehalf = attrs['lk.publish_on_behalf'];
        const transcribedTrackId = attrs['lk.transcribed_track_id'];
        const isLocal = Boolean(
          (publishOnBehalf && publishOnBehalf === localIdentity) ||
          (transcribedTrackId && localMicSid && transcribedTrackId === localMicSid) ||
          (info.senderIdentity && info.senderIdentity === localIdentity) ||
          (participantInfo?.identity && participantInfo.identity === localIdentity)
        );

        let fullText = '';

        try {
          for await (const chunk of reader) {
            if (!chunk) continue;
            fullText += chunk; // Accumulate incoming delta stream chunks into full sentence

            if (isLocal) {
              onEvent?.({ event: 'user_partial_transcript', payload: { text: fullText } });
            } else {
              onEvent?.({ event: 'tts_audio_meta', payload: { text: fullText, is_streaming: true } });
            }
          }
        } catch (e) {
          console.warn('[LiveKit] TextStream error:', e);
        }

        // Stream completed
        const finalClean = fullText.trim();
        if (finalClean) {
          if (isLocal) {
            onEvent?.({ event: 'user_transcript', payload: { text: finalClean } });
          } else {
            onEvent?.({ event: 'tts_audio_meta', payload: { text: finalClean, is_streaming: false } });
            onEvent?.({ event: 'tts_stream_end', payload: {} });
          }
        }
      });

      // Legacy TranscriptionReceived fallback — LiveKit 1.x Event Protocol
      room.on(RoomEvent.TranscriptionReceived, (segments, participant) => {
        if (!segments || segments.length === 0) return;

        for (const seg of segments) {
          const isLocal = (
            participant?.identity === room.localParticipant?.identity ||
            seg.participant_identity === room.localParticipant?.identity
          );
          const text = seg.text?.trim();
          if (!text) continue;

          if (isLocal) {
            if (seg.final) {
              onEvent?.({ event: 'user_transcript', payload: { text } });
            } else {
              onEvent?.({ event: 'user_partial_transcript', payload: { text } });
            }
          } else {
            if (seg.final) {
              onEvent?.({ event: 'tts_audio_meta', payload: { text, is_streaming: false } });
              onEvent?.({ event: 'tts_stream_end', payload: {} });
            } else {
              onEvent?.({ event: 'tts_audio_meta', payload: { text, is_streaming: true } });
            }
          }
        }
      });

      // Data channel — platform business events
      room.on(RoomEvent.DataReceived, (payload, participant, kind, topic) => {
        try {
          const msg = JSON.parse(new TextDecoder().decode(payload));
          onEvent?.(msg);
        } catch (e) {
          // Binary data — ignore
        }
      });

      // Room Disconnected & Participant Disconnected (Inactivity timeout / agent leave)
      room.on(RoomEvent.Disconnected, (reason) => {
        console.log('[LiveKit] Room disconnected:', reason);
        stopLevelLoop();
        setMuted(false);
        onStatusChange?.('disconnected');
        onEvent?.({ event: 'session_end', payload: { reason: reason || 'disconnected' } });
      });

      room.on(RoomEvent.ParticipantDisconnected, (participant) => {
        console.log('[LiveKit] Participant disconnected:', participant?.identity);
        if (participant?.identity?.startsWith('agent-')) {
          stopLevelLoop();
          setMuted(false);
          onStatusChange?.('disconnected');
          onEvent?.({ event: 'session_end', payload: { reason: 'agent_disconnected' } });
        }
      });

      // Connect to room
      await room.connect(server_url, token);
      await room.startAudio().catch(() => {});

      // Publish mic & reset mute state to active
      await room.localParticipant.setMicrophoneEnabled(true);
      setMuted(false);
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
      const friendlyMsg = (err.name === 'TypeError' && err.message?.includes('fetch'))
        ? 'Unable to reach the voice server. Please check your network connection.'
        : (err.message || 'Voice session connection failed.');
      onEvent?.({ event: 'error', payload: { message: friendlyMsg } });
      onStatusChange?.('error');
    }
  }, [createAnalyser, startLevelLoop, cleanupAudio]);

  const disconnect = useCallback(() => {
    cleanupAudio();
    setMuted(false);

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
