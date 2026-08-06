import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

/**
 * EntryGate — Full-viewport overlay with wordmark + two buttons.
 * No card, no border, no form. Just type and light in the void.
 * "Enter as Admin" dismisses gate (onEnterAdmin callback).
 * "Enter as User" navigates to /user.
 */
export function EntryGate({ open, onEnterAdmin, onAuthenticated }) {
  const navigate = useNavigate();
  const [fading, setFading] = useState(false);

  const handleAdmin = () => {
    sessionStorage.setItem('widtts_role', 'admin');
    setFading(true);
    const callback = onEnterAdmin || onAuthenticated;
    setTimeout(() => callback?.(), 600);
  };

  const handleUser = () => {
    sessionStorage.setItem('widtts_role', 'user');
    navigate('/user');
  };

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
        gap: '3rem',
        background: 'var(--void)',
        transition: 'opacity 600ms cubic-bezier(0.16, 1, 0.3, 1)',
        opacity: fading ? 0 : 1,
        pointerEvents: fading ? 'none' : 'auto',
      }}
    >
      {/* Wordmark */}
      <div style={{ textAlign: 'center' }}>
        <h1
          className="type-display"
          style={{
            fontSize: 'clamp(3rem, 8vw, 6rem)',
            fontWeight: 300,
            letterSpacing: '-0.03em',
            color: 'var(--ink-100)',
            marginBottom: '0.5rem',
          }}
        >
          widTTS
        </h1>
        <p
          className="type-micro"
          style={{
            fontSize: '12px',
            letterSpacing: '0.2em',
            color: 'var(--ink-35)',
          }}
        >
          VOICE PLATFORM
        </p>
      </div>

      {/* Two minimal text buttons */}
      <div style={{ display: 'flex', gap: '2rem', alignItems: 'center' }}>
        <button
          onClick={handleAdmin}
          style={{
            background: 'transparent',
            border: '1px solid rgba(255,255,255,0.12)',
            borderRadius: '8px',
            padding: '14px 36px',
            color: 'var(--ink-60)',
            fontFamily: 'var(--font-body)',
            fontSize: '14px',
            fontWeight: 500,
            cursor: 'pointer',
            transition: 'all 200ms cubic-bezier(0.16, 1, 0.3, 1)',
            letterSpacing: '0.02em',
          }}
          onMouseEnter={(e) => {
            e.target.style.borderColor = 'var(--accent-mid)';
            e.target.style.color = 'var(--accent-bright)';
          }}
          onMouseLeave={(e) => {
            e.target.style.borderColor = 'rgba(255,255,255,0.12)';
            e.target.style.color = 'var(--ink-60)';
          }}
          aria-label="Enter as Admin"
        >
          Enter as Admin
        </button>

        <button
          onClick={handleUser}
          style={{
            background: 'transparent',
            border: '1px solid rgba(255,255,255,0.12)',
            borderRadius: '8px',
            padding: '14px 36px',
            color: 'var(--ink-60)',
            fontFamily: 'var(--font-body)',
            fontSize: '14px',
            fontWeight: 500,
            cursor: 'pointer',
            transition: 'all 200ms cubic-bezier(0.16, 1, 0.3, 1)',
            letterSpacing: '0.02em',
          }}
          onMouseEnter={(e) => {
            e.target.style.borderColor = 'var(--accent-mid)';
            e.target.style.color = 'var(--accent-bright)';
          }}
          onMouseLeave={(e) => {
            e.target.style.borderColor = 'rgba(255,255,255,0.12)';
            e.target.style.color = 'var(--ink-60)';
          }}
          aria-label="Enter as User"
        >
          Enter as User
        </button>
      </div>
    </div>
  );
}
