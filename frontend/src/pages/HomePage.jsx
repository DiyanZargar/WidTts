import React, { useCallback, useEffect, useRef, useState, useMemo } from 'react';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { useVoiceSession } from '../hooks/useVoiceSession';
import { MicIcon, MicMutedIcon } from '../components/icons/MicIcons';
import { SettingsIcon } from '../components/icons/SettingsIcon';
import { HaloParticleVoid } from '../components/common/HaloParticleVoid';
import '../design/halo.css';

/**
 * HomePage — User-facing voice session page.
 *
 * HALO UI: Pure CSS reflective sphere driven by a single data-state attribute.
 * No Three.js, no WebGL — just DOM + CSS for all visual state changes.
 * Consumes the same useVoiceSession state and amplitude values.
 */
export default function HomePage() {
  const navigate = useNavigate();
  const params = useParams();
  const location = useLocation();
  const botSlug = params.slug || sessionStorage.getItem('active_bot_slug') || sessionStorage.getItem('widtts_bot_slug') || null;

  // Retrieve any passed or cached bot metadata so name renders instantly with no placeholder flash
  const passedBot = location.state?.bot;
  const cachedName = sessionStorage.getItem('active_bot_name') || '';
  const cachedDesc = sessionStorage.getItem('active_bot_desc') || '';

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

  const [started, setStarted] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const orbRef = useRef(null);
  const rafRef = useRef(null);
  const transcriptScrollRef = useRef(null);

  // Fetch active bot runtime info from API (empty by default — no placeholder flash)
  const [bot, setBot] = useState({
    name: passedBot?.name || cachedName || '',
    description: passedBot?.description || cachedDesc || '',
    llmModel: '',
    speechModel: '',
  });

  // Update page title with bot name
  useEffect(() => {
    if (bot.name) {
      document.title = `${bot.name}`;
    }
    return () => { document.title = 'Voice Platform'; };
  }, [bot.name]);

  useEffect(() => {
    if (botSlug) {
      fetch(`/api/bot/${botSlug}`)
        .then((r) => r.json())
        .then((data) => {
          if (data?.name) {
            setBot((prev) => ({
              ...prev,
              name: data.name || '',
              description: data.description || '',
            }));
          }
        })
        .catch(() => { });
    } else {
      fetch('/admin/api/runtime/stats')
        .then((r) => r.json())
        .then((data) => {
          if (data?.active_bot) {
            const ab = data.active_bot;
            setBot({
              name: ab.name || '',
              description: ab.description || ab.system_prompt || '',
              llmModel: ab.llm_model || '',
              speechModel: '',
            });
          }
        })
        .catch(() => { });
    }
  }, [botSlug]);

  // Auto-scroll transcript container to bottom whenever new lines/partials arrive
  useEffect(() => {
    if (transcriptScrollRef.current) {
      transcriptScrollRef.current.scrollTop = transcriptScrollRef.current.scrollHeight;
    }
  }, [transcriptLines, partialTranscript, partialAssistantTranscript]);

  // ─── Halo data-state:
  // idle -> silver before start
  // connecting / listening -> warm amber ready tone with breathing
  // user_speaking -> warm amber + amplitude reactivity
  // speaking -> warm saturated amber + TTS amplitude reactivity
  // thinking -> cool violet pulse
  // error -> muted red
  const [voiceError, setVoiceError] = useState(false);

  // Track voice errors from session events
  useEffect(() => {
    if (status === 'idle' && !isActive && started) {
      setVoiceError(true);
    } else if (isActive) {
      setVoiceError(false);
    }
  }, [status, isActive, started]);

  const haloState = useMemo(() => {
    if (voiceError && !isActive && started) return 'error';
    if (!isActive && !started) return 'idle';
    if (status === 'listening' && partialTranscript) return 'user_speaking';
    return status;
  }, [status, partialTranscript, isActive, started, voiceError]);

  // ─── Amplitude rAF loop: write --amp on orb only during reactive states
  useEffect(() => {
    const orb = orbRef.current;
    if (!orb) return;

    const isReactive = haloState === 'user_speaking' || haloState === 'speaking';
    if (!isReactive) {
      orb.style.removeProperty('--amp');
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      return;
    }

    const tick = () => {
      rafRef.current = requestAnimationFrame(tick);
      const amp = haloState === 'user_speaking' ? listenLevel : audioLevel;
      orb.style.setProperty('--amp', String(Math.min(1, amp)));
    };
    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      orb.style.removeProperty('--amp');
    };
  }, [haloState]);

  // ─── Session handlers
  const handleStart = useCallback(() => {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        const tempCtx = new AudioCtx();
        tempCtx.resume().then(() => tempCtx.close());
      }
    } catch (e) { }

    setVoiceError(false);
    setStarted(true);
    begin();
  }, [begin]);

  const handleStop = useCallback(() => {
    end();
    setStarted(false);
    setVoiceError(false);
  }, [end]);

  const handleExit = useCallback(() => {
    if (isActive) end();
    sessionStorage.removeItem('active_bot_slug');
    sessionStorage.removeItem('widtts_bot_slug');
    sessionStorage.removeItem('active_bot_name');
    sessionStorage.removeItem('active_bot_desc');
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

  // ─── Human-readable status label for the topbar
  const statusLabel = useMemo(() => {
    switch (haloState) {
      case 'user_speaking': return 'Listening';
      case 'listening': return 'Ready';
      case 'speaking': return 'Responding';
      case 'thinking': return 'Thinking';
      case 'connecting': return 'Connecting';
      case 'error': return 'Connection lost';
      case 'disconnected': return 'Disconnected';
      default: return 'Idle';
    }
  }, [haloState]);

  const hasTranscript = started && (
    transcriptLines.length > 0 ||
    Boolean(partialTranscript) ||
    Boolean(partialAssistantTranscript)
  );

  return (
    <div className="halo" data-state={haloState}>
      {/* ── Ambient Cosmic Stardust Particles ── */}
      <HaloParticleVoid />

      {/* ── Topbar ── */}
      <div className="halo__topbar">
        <span className="halo__label">{bot.name}</span>
        <div className="halo__status">
          <span className="halo__status-dot" />
          <span className="halo__status-text">{statusLabel}</span>
        </div>
      </div>

      {/* ── Orb Stage ── */}
      <div className="halo__stage">
        <div className="halo__orb" ref={orbRef} />
        <div className="halo__listen-ring" />
        <div className="halo__contact-shadow" />
        <div className="halo__reflection">
          <div className="halo__reflection-inner" />
        </div>
      </div>

      {/* ── Transcript: Growing, Scrollable, Fading History ── */}
      <div className="halo__transcript-area">
        {hasTranscript && (
          <div className="halo__transcript-scroll" ref={transcriptScrollRef}>
            {transcriptLines.map((line) => {
              if (line.speaker === 'assistant') {
                return (
                  <div className="halo__card" key={line.id}>
                    <div className="halo__card-label">{bot.name || 'Assistant'}</div>
                    <div className="halo__card-text">{line.text}</div>
                  </div>
                );
              }
              return (
                <div className="halo__user-line" key={line.id}>
                  <div className="halo__card-label">You</div>
                  <div className="halo__card-text">{line.text}</div>
                </div>
              );
            })}

            {/* Live Streaming Assistant Speech */}
            {partialAssistantTranscript && (
              <div className="halo__card halo--streaming" key="streaming-assistant">
                <div className="halo__card-label">{bot.name || 'Assistant'}</div>
                <div className="halo__card-text">{partialAssistantTranscript}</div>
              </div>
            )}

            {/* Live User Speech (Partial STT) */}
            {partialTranscript && (
              <div className="halo__user-line halo--partial" key="partial-user">
                <div className="halo__card-label">You</div>
                <div className="halo__card-text">{partialTranscript}</div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Controls ── */}
      {!started ? (
        <div className="halo__controls">
          <button className="halo__connect-btn" onClick={handleStart}>
            Connect
          </button>
        </div>
      ) : (
        <div className="halo__controls">
          <button
            className={`halo__btn${muted ? ' halo__btn--muted' : ''}`}
            onClick={() => setMuted(!muted)}
            title={muted ? 'Unmute microphone' : 'Mute microphone'}
            aria-label={muted ? 'Unmute microphone' : 'Mute microphone'}
          >
            {muted ? <MicMutedIcon size={18} /> : <MicIcon size={18} />}
          </button>
          <button className="halo__end-session" onClick={handleStop}>
            End session
          </button>
          <button
            className="halo__btn"
            title="Assistant Details"
            aria-label="Assistant Details"
            onClick={() => setShowSettingsModal(true)}
          >
            <SettingsIcon size={18} />
          </button>
        </div>
      )}

      {/* ── Bot Description & Info Modal ── */}
      {showSettingsModal && (
        <div
          className="halo__modal-backdrop"
          onClick={() => setShowSettingsModal(false)}
          role="dialog"
          aria-modal="true"
        >
          <div className="halo__modal" onClick={(e) => e.stopPropagation()}>
            <div className="halo__modal-header">
              <h3 className="halo__modal-title">{bot.name || 'Assistant Info'}</h3>
              <button
                className="halo__modal-close"
                onClick={() => setShowSettingsModal(false)}
                aria-label="Close modal"
              >
                ✕
              </button>
            </div>
            <div className="halo__modal-body">
              {bot.description || 'No description available for this assistant.'}
            </div>
            <div className="halo__modal-footer">
              <button
                className="halo__modal-btn halo__modal-btn--secondary"
                onClick={() => setShowSettingsModal(false)}
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
