import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

/**
 * BotLanding — User-facing page at /bot/:slug.
 * Shows the bot name + a single "Enter" button.
 * After clicking Enter, loads the full voice experience (HomePage).
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
      document.title = `${bot.name} — widTTS`;
    }
    return () => {
      document.title = 'widTTS — Voice Platform';
    };
  }, [bot?.name]);

  const handleEnter = useCallback(() => {
    // Store the bot slug so the voice session knows which bot to connect to
    sessionStorage.setItem('widtts_bot_slug', slug);
    setEntering(true);
    setTimeout(() => {
      navigate(`/bot/${slug}/session`);
    }, 600);
  }, [slug, navigate]);

  if (loading) {
    return (
      <div style={{
        position: 'fixed', inset: 0, background: '#050507',
        display: 'grid', placeItems: 'center',
      }}>
        <p style={{ color: 'var(--ink-35)', fontSize: '13px' }}>Loading...</p>
      </div>
    );
  }

  if (error || !bot) {
    return (
      <div style={{
        position: 'fixed', inset: 0, background: '#050507',
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', gap: '1.5rem',
      }}>
        <h1 style={{
          fontFamily: 'var(--font-display)', fontSize: '2rem',
          fontWeight: 300, color: 'var(--ink-100)',
        }}>
          widTTS
        </h1>
        <p style={{ color: 'var(--ink-35)', fontSize: '14px' }}>
          {error || 'Bot not found'}
        </p>
      </div>
    );
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 100,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '2.5rem',
        background: '#050507',
        transition: 'opacity 600ms cubic-bezier(0.16, 1, 0.3, 1)',
        opacity: entering ? 0 : 1,
        pointerEvents: entering ? 'none' : 'auto',
      }}
    >
      {/* Bot identity */}
      <div style={{ textAlign: 'center' }}>
        <h1
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: 'clamp(2.5rem, 6vw, 4.5rem)',
            fontWeight: 300,
            letterSpacing: '-0.03em',
            color: 'var(--ink-100)',
            marginBottom: '0.5rem',
          }}
        >
          {bot.name}
        </h1>
      </div>

      {/* Enter button */}
      <button
        onClick={handleEnter}
        style={{
          background: 'transparent',
          border: '1px solid var(--accent-mid)',
          borderRadius: '8px',
          padding: '14px 48px',
          color: 'var(--accent-bright)',
          fontFamily: 'var(--font-body)',
          fontSize: '14px',
          fontWeight: 500,
          cursor: 'pointer',
          transition: 'all 200ms cubic-bezier(0.16, 1, 0.3, 1)',
          letterSpacing: '0.05em',
          boxShadow: '0 0 25px 2px hsla(155, 95%, 58%, 0.2)',
        }}
        onMouseEnter={(e) => {
          e.target.style.borderColor = 'var(--accent-bright)';
          e.target.style.boxShadow = '0 0 35px 6px hsla(155, 95%, 58%, 0.4)';
          e.target.style.transform = 'scale(1.04)';
        }}
        onMouseLeave={(e) => {
          e.target.style.borderColor = 'var(--accent-mid)';
          e.target.style.boxShadow = '0 0 25px 2px hsla(155, 95%, 58%, 0.2)';
          e.target.style.transform = 'scale(1)';
        }}
        aria-label="Enter voice session"
      >
        Enter
      </button>
    </div>
  );
}
