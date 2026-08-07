import { useContext, useCallback, useMemo } from 'react';
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

  // Event handler: map LiveKit data channel events to ConversationContext actions
  const onEvent = useCallback((evt) => {
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
        dispatch({
          type: 'APPEND_TRANSCRIPT_LINE',
          line: { id: Date.now(), speaker: 'assistant', text: evt.payload.text, isHighlighted: true },
        });
        dispatch({ type: 'SET_ASSISTANT_HIGHLIGHT', value: true });
        break;
      case 'tts_stream_end':
        dispatch({ type: 'SET_ASSISTANT_HIGHLIGHT', value: false });
        break;
      case 'session_completed':
        dispatch({ type: 'SESSION_COMPLETED' });
        break;
      case 'session_reset':
        dispatch({ type: 'SESSION_RESET' });
        break;
      case 'error':
        console.warn('[Session] Error:', evt.payload.message);
        break;
    }
  }, [dispatch]);

  const onStatusChange = useCallback((status) => {
    if (status === 'connected') {
      dispatch({ type: 'SET_LISTENING', value: true });
    } else if (status === 'disconnected') {
      dispatch({ type: 'SET_LISTENING', value: false });
    }
  }, [dispatch]);

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
    connect(onEvent, onStatusChange);
  }, [dispatch, connect, onEvent, onStatusChange]);

  const end = useCallback(() => {
    disconnect();
    dispatch({ type: 'CLOSE_WIDGET' });
  }, [disconnect, dispatch]);

  const restart = useCallback(() => {
    disconnect();
    dispatch({ type: 'RESET_FOR_NEW_SESSION' });
    setTimeout(() => {
      connect(onEvent, onStatusChange);
    }, 100);
  }, [disconnect, dispatch, connect, onEvent, onStatusChange]);

  return {
    status,
    audioLevel,
    listenLevel,
    transcript,
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
