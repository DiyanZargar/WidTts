import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { HaloParticleVoid } from '../components/common/HaloParticleVoid';
import '../design/halo.css';

/**
 * BotLanding — User-facing landing page at /bot/:slug.
 * Features the Silver Halo in its inactive living breathing state with cosmic particles.
 */
export default function BotLanding() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [bot, setBot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [entering, setEntering] = useState(false);

  useEffect(() => {
    fetch(`/api/bot/${slug}`)
      .then((r) => {
        if (!r.ok) throw new Error('Bot not found');
        return r.json();
      })
      .then((data) => {
        setBot(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [slug]);

  // Set browser tab title to bot name
  useEffect(() => {
    if (bot?.name) {
      document.title = `${bot.name}`;
    }
    return () => {
      document.title = 'Voice Platform';
    };
  }, [bot?.name]);

  const handleEnter = useCallback(() => {
    sessionStorage.setItem('active_bot_slug', slug);
    sessionStorage.setItem('widtts_bot_slug', slug);
    if (bot?.name) {
      sessionStorage.setItem('active_bot_name', bot.name);
      sessionStorage.setItem('active_bot_desc', bot.description || '');
    }
    setEntering(true);
    setTimeout(() => {
      navigate(`/bot/${slug}/session`, { state: { bot } });
    }, 500);
  }, [slug, navigate, bot]);

  if (loading) {
    return (
      <div className="halo" data-state="idle" style={{ justifyContent: 'center', alignItems: 'center' }}>
        <HaloParticleVoid />
        <p style={{ color: 'var(--text-muted)', fontSize: '13px', zIndex: 1 }}>Loading...</p>
      </div>
    );
  }

  if (error || !bot) {
    return (
      <div className="halo" data-state="error" style={{ justifyContent: 'center', alignItems: 'center', gap: '1.5rem' }}>
        <HaloParticleVoid />
        <h1 className="halo__label" style={{ fontSize: '1.5rem' }}>
          Assistant Not Found
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '14px', zIndex: 1 }}>
          {error || 'Unable to load assistant.'}
        </p>
      </div>
    );
  }

  return (
    <div
      className="halo"
      data-state="idle"
      style={{
        transition: 'opacity 500ms cubic-bezier(0.16, 1, 0.3, 1)',
        opacity: entering ? 0 : 1,
        pointerEvents: entering ? 'none' : 'auto',
      }}
    >
      {/* Ambient Cosmic Particles */}
      <HaloParticleVoid />

      {/* Topbar */}
      <div className="halo__topbar" style={{ zIndex: 2 }}>
        <span className="halo__label">{bot.name}</span>
        <div className="halo__status">
          <span className="halo__status-dot" />
          <span className="halo__status-text">Standby</span>
        </div>
      </div>

      {/* Orb Stage (Silver Halo breathing) */}
      <div className="halo__stage" style={{ zIndex: 2 }}>
        <div className="halo__orb" />
        <div className="halo__contact-shadow" />
        <div className="halo__reflection">
          <div className="halo__reflection-inner" />
        </div>
      </div>

      {/* Action / Enter Area */}
      <div className="halo__controls" style={{ zIndex: 2, paddingBottom: '16px' }}>
        <button
          className="halo__connect-btn"
          onClick={handleEnter}
          aria-label={`Enter ${bot.name} voice session`}
        >
          Enter Session
        </button>
      </div>
    </div>
  );
}
