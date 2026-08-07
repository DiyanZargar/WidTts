import { useState, useEffect } from 'react';

/**
 * ReviewSection — Summary of assembled bot config + activation gesture.
 * Floating text facts, no table/form recap. Activation is a single deliberate click.
 */
export function ReviewSection({ onActivated }) {
  const [bots, setBots] = useState([]);
  const [activating, setActivating] = useState(null);

  const load = () => {
    fetch('/admin/api/bots').then(r => r.json()).then(setBots).catch(() => {});
  };

  useEffect(load, []);

  const handleActivate = async (botId) => {
    setActivating(botId);
    try {
      await fetch(`/admin/api/bots/${botId}/activate`, { method: 'POST' });
      onActivated?.(botId);
      load();
    } catch (err) {
      console.error('Activation failed:', err);
    }
    setTimeout(() => setActivating(null), 1200);
  };

  const handleDelete = async (botId) => {
    await fetch(`/admin/api/bots/${botId}`, { method: 'DELETE' });
    load();
  };

  return (
    <div className="journey-section journey-section--split">
      <div className="journey-section__content">
        <div className="step-indicator">
          <span className="step-indicator__dot" />
          Step 5 of 5
        </div>

        <h2
          className="type-display type-display-lg"
          style={{ marginBottom: '0.75rem' }}
        >
          Review & Activate
        </h2>
        <p className="type-body" style={{ marginBottom: '1.5rem', maxWidth: '520px' }}>
          Review your configured bots and activate one to go live.
          Only one bot can be active at a time — activating a new bot
          will automatically deactivate the current one.
        </p>

        {bots.length === 0 ? (
          <div className="glass-pane" style={{ textAlign: 'center', padding: '3rem 2rem' }}>
            <p style={{ fontSize: '14px', color: 'var(--ink-60)', marginBottom: '0.5rem' }}>
              No bots configured yet
            </p>
            <p className="type-micro">
              Create a bot in the previous step to see it here
            </p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {bots.map(bot => (
              <div
                key={bot.id}
                className={`glass-pane ${activating === bot.id ? 'flash-success' : ''}`}
                style={{
                  padding: '1.5rem',
                  borderColor: bot.is_active ? 'var(--accent-mid)' : undefined,
                  background: bot.is_active ? 'rgba(255,255,255,0.05)' : undefined,
                }}
              >
                {/* Bot summary */}
                <div style={{ marginBottom: '1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
                    <span style={{
                      width: '8px', height: '8px', borderRadius: '50%',
                      background: bot.is_active ? 'var(--accent-bright)' : 'rgba(255,255,255,0.15)',
                      boxShadow: bot.is_active ? '0 0 8px var(--accent-mid)' : 'none',
                      transition: 'all 300ms',
                    }} />
                    <span style={{
                      fontFamily: 'var(--font-display)',
                      fontSize: '18px',
                      fontWeight: 400,
                      color: bot.is_active ? 'var(--accent-bright)' : 'var(--ink-100)',
                    }}>
                      {bot.name}
                    </span>
                    {bot.is_active && (
                      <span className="type-micro" style={{ color: 'var(--accent-bright)', fontSize: '9px' }}>
                        ACTIVE
                      </span>
                    )}
                  </div>
                  {bot.description && (
                    <p style={{ color: 'var(--ink-35)', fontSize: '13px', marginBottom: '0.75rem' }}>
                      {bot.description}
                    </p>
                  )}
                  <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
                    {bot.llm_model && (
                      <span className="type-micro">Model: {bot.llm_model}</span>
                    )}
                    {bot.system_prompt && (
                      <span className="type-micro">
                        Prompt: {bot.system_prompt.length} chars
                      </span>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div style={{ display: 'flex', gap: '0.75rem' }}>
                  {!bot.is_active && (
                    <button
                      className="action-btn action-btn--primary"
                      onClick={() => handleActivate(bot.id)}
                      disabled={activating === bot.id}
                      style={{ fontSize: '12px', padding: '8px 20px' }}
                    >
                      {activating === bot.id ? 'Activating...' : 'Activate'}
                    </button>
                  )}
                  <button
                    className="action-btn"
                    onClick={() => handleDelete(bot.id)}
                    style={{
                      fontSize: '12px', padding: '8px 16px',
                      borderColor: 'rgba(255,255,255,0.08)', color: 'var(--ink-35)',
                    }}
                    onMouseEnter={e => { e.target.style.borderColor = 'var(--warn)'; e.target.style.color = 'var(--warn)'; }}
                    onMouseLeave={e => { e.target.style.borderColor = 'rgba(255,255,255,0.08)'; e.target.style.color = 'var(--ink-35)'; }}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Sidebar hints */}
      <div className="journey-section__sidebar">
        <div className="section-hint">
          <div className="section-hint__title">Activation</div>
          <div className="section-hint__body">
            Activating a bot makes it the live responder for all incoming
            voice sessions. Users connecting at /user will talk to this bot.
          </div>
        </div>

        <div className="section-hint">
          <div className="section-hint__title">Hot swapping</div>
          <div className="section-hint__body">
            You can switch between bots without downtime.
            Active sessions finish with the current bot — new sessions
            pick up the newly activated one.
          </div>
        </div>

        <div className="section-hint">
          <div className="section-hint__title">What's next</div>
          <div className="section-hint__body">
            Once activated, scroll to the Live section to monitor
            real-time stats, active sessions, and system health.
          </div>
        </div>
      </div>
    </div>
  );
}
