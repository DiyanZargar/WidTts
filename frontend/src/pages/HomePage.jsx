import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Canvas } from '@react-three/fiber';
import { Core } from '../components/three/Core';
import { UserParticleVoid } from '../components/journey/ParticleVoid';
import { useVoiceSession } from '../hooks/useVoiceSession';
import { useMicLevel } from '../hooks/useMicLevel';
import { useReducedMotion } from '../hooks/useReducedMotion';
import { tokens, userPalette } from '../design/tokens';
import { MicIcon, MicMutedIcon } from '../components/icons/MicIcons';

/**
 * HomePage — User Portal (`/user`)
 *
 * Full-viewport vibrant radiant emerald energy sphere + edge-to-edge floating particle void.
 * - Real-time Voice Reactivity (STT user mic input + TTS bot audio output drive orb distortion & pulse).
 * - Full conversation transcript feed & real-time assistant responses.
 * - Automatic greeting audio upon session initialization.
 * - Clean top-right EXIT navigation.
 */
export default function HomePage() {
  const navigate = useNavigate();
  const { status, audioLevel, transcript, begin, end, restart, micStream, muted, setMuted, isActive } = useVoiceSession();
  const listenLevel = useMicLevel(micStream);
  const reducedMotion = useReducedMotion();
  const [started, setStarted] = useState(false);

  // Fetch active bot runtime info from API
  const [bot, setBot] = useState({
    name: 'Voice Assistant',
    description: 'Real-time Conversational Assistant',
    llmModel: '',
    speechModel: '',
  });

  useEffect(() => {
    fetch('/admin/api/runtime/stats')
      .then((r) => r.json())
      .then((data) => {
        if (data?.active_bot) {
          const ab = data.active_bot;
          const sp = ab.speech_provider;
          setBot({
            name: ab.name || 'Voice Assistant',
            description: ab.description || ab.system_prompt || 'Real-time Conversational Assistant',
            llmModel: ab.llm_model || '',
            speechModel: sp ? `${sp.provider_type?.toUpperCase()} (${sp.stt_model || sp.tts_model})` : '',
          });
        }
      })
      .catch(() => {});
  }, []);

  const handleStart = useCallback(() => {
    // Explicitly resume browser AudioContext on user gesture to guarantee sound output
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
    navigate('/');
  }, [end, isActive, navigate]);

  // Keep started state in sync with session activity
  useEffect(() => {
    if (isActive) {
      setStarted(true);
    } else if (status === 'idle') {
      setStarted(false);
    }
  }, [isActive, status]);

  // Status badge label
  const getStatusBadge = () => {
    if (status === 'speaking') return { label: '🔊 Speaking...', color: userPalette.bright };
    if (status === 'listening') return { label: '🎙 Listening...', color: 'hsl(160, 90%, 45%)' };
    if (status === 'thinking') return { label: '🧠 Thinking...', color: 'hsl(45, 95%, 60%)' };
    if (status === 'connecting') return { label: '⏳ Connecting...', color: tokens.color.ink60 };
    return { label: '● Ready', color: userPalette.bright };
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
      {/* Viewport border glow lines */}
      <div className="viewport-border viewport-border--top viewport-border--user" />
      <div className="viewport-border viewport-border--bottom viewport-border--user" />
      <div className="viewport-border viewport-border--left viewport-border--user" />
      <div className="viewport-border viewport-border--right viewport-border--user" />

      {/* FULL-SCREEN 3D Canvas */}
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
          camera={{ fov: 45, position: [0, 0, 8] }}
          gl={{ alpha: true, antialias: true }}
          style={{ background: 'transparent', width: '100%', height: '100%' }}
        >
          {/* Particles across full viewport */}
          <UserParticleVoid />

          {/* Central Radiant Emerald Energy Orb */}
          <Core
            status={reducedMotion ? 'idle' : status}
            audioLevel={audioLevel}
            listenLevel={listenLevel}
            radius={1.35}
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
          {/* Live Conversation Transcript Feed Overlay */}
          <div
            style={{
              width: '100%',
              minHeight: '60px',
              maxHeight: '120px',
              overflowY: 'auto',
              padding: '12px 18px',
              background: 'rgba(4, 13, 10, 0.75)',
              backdropFilter: 'blur(16px)',
              WebkitBackdropFilter: 'blur(16px)',
              border: '1px solid rgba(255,255,255,0.15)',
              borderRadius: '10px',
              color: tokens.color.ink100,
              fontSize: '14px',
              fontFamily: tokens.font.body,
              textAlign: 'center',
              boxShadow: '0 0 30px rgba(0,0,0,0.6), 0 0 15px hsla(155, 95%, 58%, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {transcript ? (
              <span>"{transcript}"</span>
            ) : (
              <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: '12px' }}>
                {status === 'speaking' ? 'Assistant is speaking...' : status === 'listening' ? 'Listening to your voice...' : 'Speak now or listen to assistant...'}
              </span>
            )}
          </div>

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
