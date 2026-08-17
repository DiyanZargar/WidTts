import { useContext, useCallback, useMemo, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { ConversationContext } from '../context/ConversationContext';
import { useLiveKitRoom } from './useLiveKitRoom';

/**
 * useVoiceSession — Thin adapter around LiveKit Room + ConversationContext.
 * Exposes { status, audioLevel, listenLevel, transcript, begin, end, restart, muted, setMuted }
 * in the shape Core and UserPortal expect.
 */
export function useVoiceSession() {
  const { state, dispatch } = useContext(ConversationContext);
  const { connect, disconnect, toggleMute, sendData, muted, setMuted, audioLevel, listenLevel } = useLiveKitRoom();

  // Resolve bot slug from URL params first (works after reload / direct nav),
  // then fall back to sessionStorage (set by BotLanding on normal entry).
  const { slug: urlSlug } = useParams();
  const _resolveBotSlug = useCallback(
    () => urlSlug || sessionStorage.getItem('widtts_bot_slug') || null,
    [urlSlug],
  );

  // Event handler: map LiveKit data channel events to ConversationContext actions
  const onEventRef = useRef();
  onEventRef.current = (evt) => {
    if (!evt || !evt.event) return;

    switch (evt.event) {
      case 'session_started':
        dispatch({ type: 'SESSION_STARTED', sessionId: evt.payload.session_id });
        break;
      case 'user_partial_transcript':
        dispatch({ type: 'SET_PARTIAL_TRANSCRIPT', text: evt.payload.text });
        break;
      case 'user_transcript':
        dispatch({
          type: 'APPEND_TRANSCRIPT_LINE',
          line: { id: Date.now(), speaker: 'user', text: evt.payload.text, isHighlighted: false },
        });
        dispatch({ type: 'CLEAR_PARTIAL_TRANSCRIPT' });
        break;
      case 'tts_audio_meta':
        if (evt.payload?.is_streaming) {
          dispatch({ type: 'SET_PARTIAL_ASSISTANT_TRANSCRIPT', text: evt.payload.text });
        } else {
          dispatch({
            type: 'APPEND_TRANSCRIPT_LINE',
            line: { id: Date.now(), speaker: 'assistant', text: evt.payload.text, isHighlighted: true },
          });
          dispatch({ type: 'CLEAR_PARTIAL_ASSISTANT_TRANSCRIPT' });
        }
        dispatch({ type: 'SET_ASSISTANT_HIGHLIGHT', value: true });
        break;
      case 'tts_stream_end':
        dispatch({ type: 'CLEAR_PARTIAL_ASSISTANT_TRANSCRIPT' });
        dispatch({ type: 'SET_ASSISTANT_HIGHLIGHT', value: false });
        break;
      case 'session_completed':
      case 'session_end':
      case 'session_timeout':
      case 'room_disconnected':
        dispatch({ type: 'CLOSE_WIDGET' });
        dispatch({ type: 'SET_LISTENING', value: false });
        dispatch({ type: 'SET_SPEAKING', value: false });
        break;
      case 'session_reset':
        dispatch({ type: 'SESSION_RESET' });
        break;
      case 'error':
        console.warn('[Session] Error:', evt.payload.message);
        break;
    }
  };

  const onStatusChangeRef = useRef();
  onStatusChangeRef.current = (status) => {
    if (status === 'connected') {
      dispatch({ type: 'SET_LISTENING', value: true });
    } else if (status === 'disconnected') {
      dispatch({ type: 'SET_LISTENING', value: false });
    }
  };

  const stableOnEvent = useCallback((evt) => onEventRef.current?.(evt), []);
  const stableOnStatusChange = useCallback((s) => onStatusChangeRef.current?.(s), []);

  // Map conversation state to simplified BotStatus
  const status = useMemo(() => {
    if (!state.isOpen) return 'idle';
    if (state.status === 'connecting') return 'connecting';
    if (state.status === 'completed' || state.status === 'cancelled') return 'idle';
    if (state.isSpeaking) return 'speaking';
    if (state.isListening) return 'listening';
    if (state.status === 'active') return 'thinking';
    return 'idle';
  }, [state.isOpen, state.status, state.isSpeaking, state.isListening]);

  // Single transcript line
  const transcript = useMemo(() => {
    if (state.partialTranscript) return state.partialTranscript;
    const lines = state.transcriptLines;
    if (lines && lines.length > 0) return lines[lines.length - 1]?.text || '';
    return '';
  }, [state.transcriptLines, state.partialTranscript]);

  const begin = useCallback(() => {
    dispatch({ type: 'OPEN_WIDGET' });
    const botSlug = _resolveBotSlug();
    connect(stableOnEvent, stableOnStatusChange, botSlug);
  }, [dispatch, connect, stableOnEvent, stableOnStatusChange, _resolveBotSlug]);

  const end = useCallback(() => {
    disconnect();
    dispatch({ type: 'CLOSE_WIDGET' });
  }, [disconnect, dispatch]);

  const restart = useCallback(() => {
    disconnect();
    dispatch({ type: 'RESET_FOR_NEW_SESSION' });
    setTimeout(() => {
      const botSlug = _resolveBotSlug();
      connect(stableOnEvent, stableOnStatusChange, botSlug);
    }, 100);
  }, [disconnect, dispatch, connect, stableOnEvent, stableOnStatusChange, _resolveBotSlug]);

  return {
    status,
    audioLevel,
    listenLevel,
    transcript,
    transcriptLines: state.transcriptLines || [],
    partialTranscript: state.partialTranscript || '',
    partialAssistantTranscript: state.partialAssistantTranscript || '',
    begin,
    end,
    restart,
    micStream: null,
    muted,
    setMuted,
    isCompleted: state.status === 'completed',
    isCancelled: state.status === 'cancelled',
    isActive: state.isOpen && state.status !== 'completed' && state.status !== 'cancelled',
  };
}
