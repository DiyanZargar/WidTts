import { useState, useEffect } from 'react';

/**
 * LiveSection — Final resting section.
 * The Core in its operational state, with readouts in glass panes:
 * active session count, status, DB health.
 */
export function LiveSection() {
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);

  useEffect(() => {
    const load = () => {
      fetch('/admin/api/runtime/stats').then(r => r.json()).then(setStats).catch(() => {});
      fetch('/admin/api/runtime/health').then(r => r.json()).then(setHealth).catch(() => {});
    };
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="journey-section journey-section--split">
      <div className="journey-section__content">
        <div className="step-indicator">
          <span className="step-indicator__dot" style={{
            background: stats?.active_bot ? 'var(--accent-bright)' : 'var(--ink-35)',
            boxShadow: stats?.active_bot ? '0 0 8px var(--accent-mid)' : 'none',
          }} />
          {stats?.active_bot ? 'Operational' : 'Standby'}
        </div>

        <h2
          className="type-display type-display-lg"
          style={{ marginBottom: '0.75rem' }}
        >
          Live
        </h2>
        <p className="type-body" style={{ marginBottom: '2rem', maxWidth: '520px' }}>
          Your bot is ready. Monitor its operational state in real-time.
          Stats refresh every 5 seconds automatically.
        </p>

        {/* Stat cards in glass panes */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '1rem',
          marginBottom: '2rem',
        }}>
          <div className="glass-pane" style={{ textAlign: 'center', padding: '1.5rem 1rem' }}>
            <span
              className="type-display"
              style={{
                fontSize: '2.5rem',
                fontWeight: 300,
                color: stats?.active_bot ? 'var(--accent-bright)' : 'var(--ink-35)',
                display: 'block',
              }}
            >
              {stats?.active_bot ? '●' : '○'}
            </span>
            <span className="type-micro" style={{ marginTop: '0.75rem', display: 'block' }}>
              {stats?.active_bot?.name || 'No Active Bot'}
            </span>
          </div>

          <div className="glass-pane" style={{ textAlign: 'center', padding: '1.5rem 1rem' }}>
            <span
              className="type-display"
              style={{
                fontSize: '2.5rem',
                fontWeight: 300,
                color: 'var(--accent-bright)',
                display: 'block',
              }}
            >
              {stats?.active_sessions ?? '—'}
            </span>
            <span className="type-micro" style={{ marginTop: '0.75rem', display: 'block' }}>
              Active Sessions
            </span>
          </div>

          <div className="glass-pane" style={{ textAlign: 'center', padding: '1.5rem 1rem' }}>
            <span
              className="type-display"
              style={{
                fontSize: '2.5rem',
                fontWeight: 300,
                color: health?.status === 'ok' ? 'var(--accent-bright)' : 'var(--warn)',
                display: 'block',
              }}
            >
              {health?.status === 'ok' ? '●' : '○'}
            </span>
            <span className="type-micro" style={{ marginTop: '0.75rem', display: 'block' }}>
              Database
            </span>
          </div>
        </div>

        {/* Secondary stats in a glass pane */}
        <div className="glass-pane" style={{ padding: '1.25rem 1.5rem' }}>
          <span className="type-micro" style={{ display: 'block', marginBottom: '1rem' }}>
            Platform Overview
          </span>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: '1.5rem',
          }}>
            <div>
              <span style={{ display: 'block', fontSize: '24px', fontWeight: 300, fontFamily: 'var(--font-display)', color: 'var(--ink-100)' }}>
                {stats?.bots ?? 0}
              </span>
              <span className="type-micro">Bots</span>
            </div>
            <div>
              <span style={{ display: 'block', fontSize: '24px', fontWeight: 300, fontFamily: 'var(--font-display)', color: 'var(--ink-100)' }}>
                {stats?.llm_providers ?? 0}
              </span>
              <span className="type-micro">LLM Providers</span>
            </div>
            <div>
              <span style={{ display: 'block', fontSize: '24px', fontWeight: 300, fontFamily: 'var(--font-display)', color: 'var(--ink-100)' }}>
                {stats?.speech_providers ?? 0}
              </span>
              <span className="type-micro">Speech Providers</span>
            </div>
          </div>
        </div>
      </div>

      {/* Sidebar hints */}
      <div className="journey-section__sidebar">
        <div className="section-hint">
          <div className="section-hint__title">User Portal</div>
          <div className="section-hint__body">
            Users connect to your bot at <span style={{ color: 'var(--accent-mid)', fontFamily: 'monospace', fontSize: '11px' }}>/user</span>.
            Share this URL to start voice conversations with the active bot.
          </div>
        </div>

        <div className="section-hint">
          <div className="section-hint__title">Auto-Refresh</div>
          <div className="section-hint__body">
            Stats update every 5 seconds. Active session count reflects
            WebSocket connections currently streaming audio.
          </div>
        </div>

        <div className="section-hint">
          <div className="section-hint__title">Health Check</div>
          <div className="section-hint__body">
            The database indicator shows PostgreSQL connectivity.
            If it goes red, check your database connection and restart
            the backend server.
          </div>
        </div>
      </div>
    </div>
  );
}
