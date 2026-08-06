import { useContext, useCallback, useMemo, useEffect, useState } from 'react';
import { ConversationContext } from '../context/ConversationContext';
import { useWebSocket } from './useWebSocket';
import { audioVolumeTracker } from '../utils/audioUtils';

/**
 * useVoiceSession — Thin adapter around existing WebSocket + ConversationContext.
 * Exposes { status, audioLevel, transcript, begin, end, restart, micStream, muted, setMuted }
 * in the shape Core and UserPortal expect.
 */
export function useVoiceSession() {
  const { state, dispatch } = useContext(ConversationContext);
  const { connect, disconnect, micStream, muted, setMuted } = useWebSocket('active_bot');
  const [audioLevel, setAudioLevel] = useState(0);

  // Poll speaker volume tracker when speaking
  useEffect(() => {
    let frameId;
    const tick = () => {
      if (audioVolumeTracker.isTTSPlaying) {
        // speaker level is roughly 0-100, normalize to 0-1
        const norm = Math.min(1, audioVolumeTracker.speaker / 100);
        setAudioLevel(norm);
      } else {
        setAudioLevel(0);
      }
      frameId = requestAnimationFrame(tick);
    };
    tick();
    return () => cancelAnimationFrame(frameId);
  }, []);

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

  // Single transcript line that replaces itself
  const transcript = useMemo(() => {
    if (state.partialTranscript) return state.partialTranscript;
    const lines = state.transcriptLines;
    if (lines && lines.length > 0) return lines[lines.length - 1]?.text || '';
    return '';
  }, [state.transcriptLines, state.partialTranscript]);

  const begin = useCallback(() => {
    dispatch({ type: 'OPEN_WIDGET' });
    connect();
  }, [dispatch, connect]);

  const end = useCallback(() => {
    disconnect();
    sessionStorage.removeItem('widget_session_id');
    dispatch({ type: 'CLOSE_WIDGET' });
  }, [disconnect, dispatch]);

  const restart = useCallback(() => {
    disconnect();
    sessionStorage.removeItem('widget_session_id');
    dispatch({ type: 'RESET_FOR_NEW_SESSION' });
    setTimeout(() => {
      connect();
    }, 100);
  }, [disconnect, dispatch, connect]);

  return {
    status,
    audioLevel,
    transcript,
    begin,
    end,
    restart,
    micStream,
    muted,
    setMuted,
    isCompleted: state.status === 'completed',
    isCancelled: state.status === 'cancelled',
    isActive: state.isOpen && state.status !== 'completed' && state.status !== 'cancelled',
  };
}
