import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Canvas } from '@react-three/fiber';
import { CoreSphere } from '../components/journey/CoreSphere';
import { UserParticleVoid } from '../components/journey/ParticleVoid';
import { useVoiceSession } from '../hooks/useVoiceSession';
import { useReducedMotion } from '../hooks/useReducedMotion';
import { tokens, userPalette } from '../design/tokens';
import { MicIcon, MicMutedIcon } from '../components/icons/MicIcons';

/**
 * HomePage — User Portal (`/user`)
 *
 * Full-viewport vibrant radiant emerald energy sphere + edge-to-edge floating particle void.
 * Reuses the exact 3D CoreSphere from admin panel with full real-time voice reactivity.
 */
export default function HomePage() {
  const navigate = useNavigate();
  const params = useParams();
  const botSlug = params.slug || sessionStorage.getItem('widtts_bot_slug') || null;
  const {
    status,
    audioLevel,
    listenLevel,
    transcriptLines,
    partialTranscript,
    partialAssistantTranscript,
    begin,
    end,
    restart,
    muted,
    setMuted,
    isActive,
  } = useVoiceSession();
  const reducedMotion = useReducedMotion();
  const [started, setStarted] = useState(false);
  const transcriptScrollRef = useRef(null);

  // Auto-scroll transcript feed container to bottom whenever new lines/partials arrive
  useEffect(() => {
    if (transcriptScrollRef.current) {
      transcriptScrollRef.current.scrollTop = transcriptScrollRef.current.scrollHeight;
    }
  }, [transcriptLines, partialTranscript, partialAssistantTranscript]);

  // Fetch active bot runtime info from API
  const [bot, setBot] = useState({
    name: 'Voice Assistant',
    description: 'Real-time Conversational Assistant',
    llmModel: '',
    speechModel: '',
  });

  useEffect(() => {
    if (botSlug) {
      // Bot-specific route — fetch from public API
      fetch(`/api/bot/${botSlug}`)
        .then((r) => r.json())
        .then((data) => {
          if (data?.name) {
            setBot({
              name: data.name || 'Voice Assistant',
              description: data.description || 'Real-time Conversational Assistant',
              llmModel: '',
              speechModel: '',
            });
          }
        })
        .catch(() => {});
    } else {
      // Admin active bot route
      fetch('/admin/api/runtime/stats')
        .then((r) => r.json())
        .then((data) => {
          if (data?.active_bot) {
            const ab = data.active_bot;
            const sttP = ab.stt_provider;
            const ttsP = ab.tts_provider;
            setBot({
              name: ab.name || 'Voice Assistant',
              description: ab.description || ab.system_prompt || 'Real-time Conversational Assistant',
              llmModel: ab.llm_model || '',
              speechModel: sttP || ttsP ? `STT: ${sttP?.name || 'N/A'} • TTS: ${ttsP?.name || 'N/A'}` : '',
            });
          }
        })
        .catch(() => {});
    }
  }, [botSlug]);

  const handleStart = useCallback(() => {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        const tempCtx = new AudioCtx();
        tempCtx.resume().then(() => tempCtx.close());
      }
    } catch (e) {}

    setStarted(true);
    begin();
  }, [begin]);

  const handleStop = useCallback(() => {
    end();
    setStarted(false);
  }, [end]);

  const handleExit = useCallback(() => {
    if (isActive) end();
    // Clear bot slug from session when exiting
    sessionStorage.removeItem('widtts_bot_slug');
    if (botSlug) {
      navigate(`/bot/${botSlug}`);
    } else {
      navigate('/');
    }
  }, [end, isActive, navigate, botSlug]);

  useEffect(() => {
    if (isActive) {
      setStarted(true);
    } else if (status === 'idle') {
      setStarted(false);
    }
  }, [isActive, status]);

  const getStatusBadge = () => {
    if (status === 'speaking') return { label: '🔊 Speaking...', color: userPalette.bright };
    if (status === 'listening') return { label: '🎙 Listening...', color: 'hsl(160, 90%, 45%)' };
    if (status === 'thinking') return { label: '🧠 Thinking...', color: 'hsl(45, 95%, 60%)' };
    if (status === 'connecting') return { label: '⏳ Connecting...', color: tokens.color.ink60 };
    if (!isActive || status === 'idle' || status === 'completed' || status === 'disconnected' || status === 'off') {
      return { label: '● SESSION OFF', color: 'hsl(350, 90%, 55%)' };
    }
    return { label: '● READY', color: userPalette.bright };
  };

  const statusBadge = getStatusBadge();

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: tokens.color.void,
        display: 'grid',
        placeItems: 'center',
        overflow: 'hidden',
        userSelect: 'none',
      }}
    >
      <div className="viewport-border viewport-border--top viewport-border--user" />
      <div className="viewport-border viewport-border--bottom viewport-border--user" />
      <div className="viewport-border viewport-border--left viewport-border--user" />
      <div className="viewport-border viewport-border--right viewport-border--user" />

      {/* FULL-SCREEN 3D Canvas with exact Admin Panel CoreSphere */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          width: '100vw',
          height: '100vh',
          pointerEvents: 'none',
          zIndex: 1,
        }}
      >
        <Canvas
          camera={{ fov: 45, position: [0, 0.4, 8.5] }}
          gl={{ alpha: true, antialias: true, powerPreference: 'high-performance' }}
          style={{ background: 'transparent', width: '100%', height: '100%' }}
        >
          <ambientLight intensity={0.15} />
          <directionalLight position={[5, 10, 5]} intensity={0.4} color="hsl(155, 95%, 58%)" />
          <pointLight position={[-5, 5, -5]} intensity={0.3} color="hsl(160, 90%, 42%)" />
          <UserParticleVoid />
          <CoreSphere
            status={status}
            isActive={isActive}
            activated={isActive}
            audioLevel={audioLevel}
            listenLevel={listenLevel}
            progress={0}
          />
        </Canvas>
      </div>

      {/* Top Navigation Bar */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: '60px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '0 32px',
          zIndex: 20,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: statusBadge.color,
              boxShadow: `0 0 10px ${statusBadge.color}`,
            }}
          />
          <span className="type-micro" style={{ color: tokens.color.ink60, fontSize: '11px' }}>
            {statusBadge.label}
          </span>
        </div>

        <button
          onClick={handleExit}
          style={{
            background: 'transparent',
            border: `1px solid ${tokens.color.ink35}`,
            color: tokens.color.ink100,
            fontFamily: tokens.font.body,
            fontWeight: 600,
            fontSize: '11px',
            letterSpacing: '0.15em',
            textTransform: 'uppercase',
            cursor: 'pointer',
            padding: '8px 18px',
            borderRadius: '4px',
            boxShadow: '0 0 12px rgba(255,255,255,0.15)',
            transition: `all ${tokens.motion.hoverMs}ms cubic-bezier(${tokens.easing.expoOut.join(',')})`,
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = tokens.color.ink100;
            e.currentTarget.style.boxShadow = '0 0 20px rgba(255,255,255,0.5)';
            e.currentTarget.style.transform = 'scale(1.04)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = tokens.color.ink35;
            e.currentTarget.style.boxShadow = '0 0 12px rgba(255,255,255,0.15)';
            e.currentTarget.style.transform = 'scale(1)';
          }}
        >
          Exit
        </button>
      </div>

      {/* Top Bot Identity */}
      <div style={{ position: 'absolute', top: '10%', textAlign: 'center', zIndex: 10, pointerEvents: 'none' }}>
        <h1
          style={{
            fontFamily: tokens.font.display,
            fontWeight: 400,
            fontSize: '32px',
            color: tokens.color.ink100,
            letterSpacing: '-0.02em',
            margin: 0,
            textShadow: '0 0 20px rgba(255,255,255,0.3)',
          }}
        >
          {bot.name}
        </h1>
        {bot.description && (
          <p
            style={{
              fontFamily: tokens.font.body,
              fontWeight: 600,
              fontSize: '11px',
              color: 'rgba(255,255,255,0.7)',
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              marginTop: '6px',
              marginBottom: 0,
              textShadow: '0 0 10px rgba(255,255,255,0.2)',
            }}
          >
            {bot.description}
          </p>
        )}
        {(bot.llmModel || bot.speechModel) && (
          <div
            style={{
              display: 'flex',
              gap: '8px',
              justifyContent: 'center',
              marginTop: '8px',
            }}
          >
            {bot.llmModel && (
              <span
                style={{
                  fontSize: '10px',
                  fontFamily: 'monospace',
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(255,255,255,0.12)',
                  color: userPalette.bright,
                  padding: '2px 8px',
                  borderRadius: '12px',
                }}
              >
                LLM: {bot.llmModel}
              </span>
            )}
            {bot.speechModel && (
              <span
                style={{
                  fontSize: '10px',
                  fontFamily: 'monospace',
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(255,255,255,0.12)',
                  color: 'rgba(255,255,255,0.8)',
                  padding: '2px 8px',
                  borderRadius: '12px',
                }}
              >
                SPEECH: {bot.speechModel}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Controls & Action Area */}
      {!started ? (
        <button
          onClick={handleStart}
          style={{
            position: 'absolute',
            bottom: '14%',
            background: 'rgba(255,255,255,0.04)',
            border: `1px solid ${userPalette.bright}`,
            color: tokens.color.ink100,
            padding: '14px 36px',
            fontFamily: tokens.font.body,
            fontWeight: 600,
            fontSize: '12px',
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
            cursor: 'pointer',
            borderRadius: '6px',
            boxShadow: `0 0 25px 2px hsla(155, 95%, 58%, 0.35)`,
            transition: `all ${tokens.motion.hoverMs}ms cubic-bezier(${tokens.easing.expoOut.join(',')})`,
            zIndex: 10,
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = userPalette.bloom;
            e.currentTarget.style.background = 'rgba(255,255,255,0.12)';
            e.currentTarget.style.boxShadow = `0 0 35px 6px hsla(155, 95%, 58%, 0.55)`;
            e.currentTarget.style.transform = 'scale(1.04)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = userPalette.bright;
            e.currentTarget.style.background = 'rgba(255,255,255,0.04)';
            e.currentTarget.style.boxShadow = `0 0 25px 2px hsla(155, 95%, 58%, 0.35)`;
            e.currentTarget.style.transform = 'scale(1)';
          }}
        >
          Initialize Core
        </button>
      ) : (
        <div
          style={{
            position: 'absolute',
            bottom: '8%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '16px',
            zIndex: 10,
            width: '90%',
            maxWidth: '560px',
          }}
        >
          {/* Live Subtitle Transcript Overlay (Minimal, Frameless) */}
          {(transcriptLines.length > 0 || partialTranscript || partialAssistantTranscript) && (
            <div
              ref={transcriptScrollRef}
              style={{
                width: '100%',
                maxHeight: '160px',
                overflowY: 'auto',
                padding: '8px 12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
                pointerEvents: 'auto',
                maskImage: 'linear-gradient(to bottom, transparent 0%, black 20%, black 100%)',
                WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, black 20%, black 100%)',
              }}
            >
              {transcriptLines.slice(-6).map((line, idx) => {
                const isUser = line.speaker === 'user';
                const isLatest = idx === Math.min(transcriptLines.length, 6) - 1 && !partialTranscript && !partialAssistantTranscript;
                return (
                  <div
                    key={line.id || idx}
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: isUser ? 'flex-end' : 'flex-start',
                      alignSelf: isUser ? 'flex-end' : 'flex-start',
                      maxWidth: '88%',
                      opacity: isLatest ? 1 : 0.65,
                      transition: 'all 300ms ease-out',
                    }}
                  >
                    <span
                      style={{
                        fontSize: '9px',
                        fontWeight: 700,
                        letterSpacing: '0.15em',
                        textTransform: 'uppercase',
                        color: isUser ? 'rgba(52, 211, 153, 0.7)' : 'rgba(103, 232, 249, 0.7)',
                        marginBottom: '2px',
                      }}
                    >
                      {isUser ? 'YOU' : (bot.name || 'AI').toUpperCase()}
                    </span>
                    <p
                      style={{
                        margin: 0,
                        fontSize: '14px',
                        lineHeight: '1.4',
                        fontWeight: isLatest ? 500 : 400,
                        color: isUser ? 'rgba(236, 253, 245, 0.95)' : 'rgba(255, 255, 255, 0.95)',
                        textShadow: isLatest ? '0 0 12px rgba(255, 255, 255, 0.2)' : 'none',
                        textAlign: isUser ? 'right' : 'left',
                      }}
                    >
                      {line.text}
                    </p>
                  </div>
                );
              })}

              {/* Live partial user STT */}
              {partialTranscript && (
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'flex-end',
                    alignSelf: 'flex-end',
                    maxWidth: '88%',
                  }}
                >
                  <span
                    style={{
                      fontSize: '9px',
                      fontWeight: 700,
                      letterSpacing: '0.15em',
                      textTransform: 'uppercase',
                      color: 'rgba(52, 211, 153, 0.9)',
                      marginBottom: '2px',
                    }}
                  >
                    YOU
                  </span>
                  <p
                    style={{
                      margin: 0,
                      fontSize: '14px',
                      lineHeight: '1.4',
                      color: 'rgba(52, 211, 153, 0.95)',
                      fontStyle: 'italic',
                      textAlign: 'right',
                    }}
                  >
                    "{partialTranscript}" <span className="animate-pulse">...</span>
                  </p>
                </div>
              )}

              {/* Live partial assistant stream */}
              {partialAssistantTranscript && (
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'flex-start',
                    alignSelf: 'flex-start',
                    maxWidth: '88%',
                  }}
                >
                  <span
                    style={{
                      fontSize: '9px',
                      fontWeight: 700,
                      letterSpacing: '0.15em',
                      textTransform: 'uppercase',
                      color: 'rgba(103, 232, 249, 0.9)',
                      marginBottom: '2px',
                    }}
                  >
                    {(bot.name || 'AI').toUpperCase()}
                  </span>
                  <p
                    style={{
                      margin: 0,
                      fontSize: '14px',
                      lineHeight: '1.4',
                      color: 'rgba(255, 255, 255, 0.95)',
                      textAlign: 'left',
                    }}
                  >
                    {partialAssistantTranscript} <span className="animate-pulse">...</span>
                  </p>
                </div>
              )}
            </div>
          )}

          <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
            <button
              onClick={() => setMuted(!muted)}
              style={{
                background: muted ? 'rgba(255, 80, 80, 0.15)' : 'rgba(255,255,255,0.06)',
                border: `1px solid ${muted ? 'rgba(255, 80, 80, 0.4)' : 'rgba(255,255,255,0.2)'}`,
                color: tokens.color.ink100,
                width: '48px',
                height: '48px',
                borderRadius: '50%',
                display: 'grid',
                placeItems: 'center',
                cursor: 'pointer',
                transition: 'all 200ms',
              }}
              title={muted ? 'Unmute microphone' : 'Mute microphone'}
            >
              {muted ? <MicMutedIcon size={20} /> : <MicIcon size={20} />}
            </button>

            <button
              onClick={handleStop}
              style={{
                background: 'rgba(255, 80, 80, 0.2)',
                border: '1px solid rgba(255, 80, 80, 0.5)',
                color: '#fff',
                padding: '12px 24px',
                fontFamily: tokens.font.body,
                fontWeight: 600,
                fontSize: '11px',
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                cursor: 'pointer',
                borderRadius: '4px',
                boxShadow: '0 0 16px rgba(255, 80, 80, 0.3)',
              }}
            >
              End Session
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
