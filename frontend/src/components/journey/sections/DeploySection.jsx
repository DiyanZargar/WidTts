import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';

/**
 * DeploySection — Deploy bots with unique shareable links.
 * Each bot can be independently deployed, generating a URL like /bot/{slug}.
 * Deployed bots show their link with copy + open icon actions.
 * Undeploy requires typing the bot name to confirm (like GitHub repo deletion).
 */
export function DeploySection({ onActivated, refreshTrigger }) {
  const [bots, setBots] = useState([]);
  const [deploying, setDeploying] = useState(null);
  const [copiedSlug, setCopiedSlug] = useState(null);
  // Undeploy confirmation modal state
  const [undeployTarget, setUndeployTarget] = useState(null); // { id, name }
  const [undeployConfirmText, setUndeployConfirmText] = useState('');

  const load = () => {
    fetch('/admin/api/bots').then(r => r.json()).then(setBots).catch(() => {});
  };

  useEffect(load, []);
  useEffect(() => { if (refreshTrigger) load(); }, [refreshTrigger]);

  const handleDeploy = async (botId) => {
    setDeploying(botId);
    try {
      await fetch(`/admin/api/bots/${botId}/deploy`, { method: 'POST' });
      load();
    } catch (err) {
      console.error('Deploy failed:', err);
    }
    setTimeout(() => setDeploying(null), 800);
  };

  const handleUndeploy = async () => {
    if (!undeployTarget) return;
    try {
      await fetch(`/admin/api/bots/${undeployTarget.id}/undeploy`, { method: 'POST' });
      load();
    } catch (err) {
      console.error('Undeploy failed:', err);
    }
    setUndeployTarget(null);
    setUndeployConfirmText('');
  };

  const handleCopyLink = (slug) => {
    const url = `${window.location.origin}/bot/${slug}`;
    navigator.clipboard.writeText(url).then(() => {
      setCopiedSlug(slug);
      setTimeout(() => setCopiedSlug(null), 2000);
    });
  };

  const handleOpenLink = (slug) => {
    window.open(`/bot/${slug}`, '_blank');
  };

  const isUndeployConfirmed = undeployTarget && undeployConfirmText === undeployTarget.name;

  return (
    <div className="journey-section journey-section--split">
      <div className="journey-section__content">
        <div className="step-indicator">
          <span className="step-indicator__dot" />
          Step 4 of 4
        </div>

        <h2
          className="type-display type-display-lg"
          style={{ marginBottom: '0.75rem' }}
        >
          Review & Deploy
        </h2>
        <p className="type-body" style={{ marginBottom: '1.5rem', maxWidth: '520px' }}>
          Deploy your configured bots to generate shareable links.
          Each bot gets its own unique URL that users can access directly.
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
                className={`glass-pane ${deploying === bot.id ? 'flash-success' : ''}`}
                style={{
                  padding: '1.5rem',
                  borderColor: bot.is_deployed ? 'var(--accent-mid)' : undefined,
                  background: bot.is_deployed ? 'rgba(255,255,255,0.05)' : undefined,
                }}
              >
                {/* Bot summary */}
                <div style={{ marginBottom: '1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
                    <span style={{
                      width: '8px', height: '8px', borderRadius: '50%',
                      background: bot.is_deployed ? 'var(--accent-bright)' : 'rgba(255,255,255,0.15)',
                      boxShadow: bot.is_deployed ? '0 0 8px var(--accent-mid)' : 'none',
                      transition: 'all 300ms',
                    }} />
                    <span style={{
                      fontFamily: 'var(--font-display)',
                      fontSize: '18px',
                      fontWeight: 400,
                      color: bot.is_deployed ? 'var(--accent-bright)' : 'var(--ink-100)',
                    }}>
                      {bot.name}
                    </span>
                    {bot.is_deployed && (
                      <span className="type-micro" style={{ color: 'var(--accent-bright)', fontSize: '9px' }}>
                        DEPLOYED
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

                {/* Deploy link — shown when deployed */}
                {bot.is_deployed && bot.deploy_slug && (
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    padding: '10px 14px',
                    marginBottom: '1rem',
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: '6px',
                  }}>
                    <span style={{
                      flex: 1,
                      fontFamily: 'monospace',
                      fontSize: '12px',
                      color: 'var(--accent-bright)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}>
                      {`${window.location.origin}/bot/${bot.deploy_slug}`}
                    </span>
                    <button
                      onClick={() => handleCopyLink(bot.deploy_slug)}
                      title={copiedSlug === bot.deploy_slug ? 'Copied!' : 'Copy link'}
                      style={{
                        background: 'rgba(255,255,255,0.06)',
                        border: '1px solid rgba(255,255,255,0.12)',
                        borderRadius: '4px',
                        padding: '6px 8px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: copiedSlug === bot.deploy_slug ? 'var(--accent-bright)' : 'var(--ink-60)',
                        transition: 'all 150ms',
                      }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent-mid)'; e.currentTarget.style.color = 'var(--accent-bright)'; }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.12)'; e.currentTarget.style.color = copiedSlug === bot.deploy_slug ? 'var(--accent-bright)' : 'var(--ink-60)'; }}
                    >
                      {copiedSlug === bot.deploy_slug ? (
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      ) : (
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                        </svg>
                      )}
                    </button>
                    <button
                      onClick={() => handleOpenLink(bot.deploy_slug)}
                      title="Open in new tab"
                      style={{
                        background: 'rgba(255,255,255,0.06)',
                        border: '1px solid rgba(255,255,255,0.12)',
                        borderRadius: '4px',
                        padding: '6px 8px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'var(--ink-60)',
                        transition: 'all 150ms',
                      }}
                      onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent-mid)'; e.currentTarget.style.color = 'var(--accent-bright)'; }}
                      onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.12)'; e.currentTarget.style.color = 'var(--ink-60)'; }}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                        <polyline points="15 3 21 3 21 9" />
                        <line x1="10" y1="14" x2="21" y2="3" />
                      </svg>
                    </button>
                  </div>
                )}

                {/* Actions */}
                <div style={{ display: 'flex', gap: '0.75rem' }}>
                  {!bot.is_deployed ? (
                    <button
                      className="action-btn action-btn--primary"
                      onClick={() => handleDeploy(bot.id)}
                      disabled={deploying === bot.id}
                      style={{ fontSize: '12px', padding: '8px 20px' }}
                    >
                      {deploying === bot.id ? 'Deploying...' : 'Deploy'}
                    </button>
                  ) : (
                    <button
                      className="action-btn"
                      onClick={() => {
                        setUndeployTarget({ id: bot.id, name: bot.name });
                        setUndeployConfirmText('');
                      }}
                      style={{
                        fontSize: '12px', padding: '8px 16px',
                        borderColor: 'rgba(255,255,255,0.08)', color: 'var(--ink-35)',
                      }}
                      onMouseEnter={e => { e.target.style.borderColor = 'var(--warn)'; e.target.style.color = 'var(--warn)'; }}
                      onMouseLeave={e => { e.target.style.borderColor = 'rgba(255,255,255,0.08)'; e.target.style.color = 'var(--ink-35)'; }}
                    >
                      Undeploy
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Sidebar hints */}
      <div className="journey-section__sidebar">
        <div className="section-hint">
          <div className="section-hint__title">Deployment</div>
          <div className="section-hint__body">
            Deploying a bot generates a unique shareable link.
            Users with this link can interact directly with that specific bot.
          </div>
        </div>

        <div className="section-hint">
          <div className="section-hint__title">Per-bot isolation</div>
          <div className="section-hint__body">
            Each deployed bot runs independently with its own configuration,
            system prompt, and LLM/speech providers.
          </div>
        </div>

        <div className="section-hint">
          <div className="section-hint__title">What's next</div>
          <div className="section-hint__body">
            Share the deploy link with your users. They'll land on a
            dedicated page for that bot and can start a voice session.
          </div>
        </div>
      </div>

      {/* Undeploy Confirmation Modal — GitHub-style name confirmation */}
      {undeployTarget && createPortal(
        <div
          style={{
            position: 'fixed',
            inset: 0,
            width: '100vw',
            height: '100vh',
            background: 'rgba(0,0,0,0.8)',
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
            display: 'grid',
            placeItems: 'center',
            zIndex: 99999,
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setUndeployTarget(null);
              setUndeployConfirmText('');
            }
          }}
        >
          <div
            className="glass-pane"
            style={{
              width: '90%',
              maxWidth: '460px',
              padding: '2rem',
              border: '1px solid rgba(16,185,129,0.2)',
              boxShadow: '0 0 50px rgba(0,0,0,0.9), 0 0 20px rgba(16,185,129,0.05)',
            }}
          >
            <h3 style={{ fontFamily: 'var(--font-display)', color: 'var(--ink-100)', marginBottom: '0.75rem', fontSize: '18px' }}>
              Undeploy bot
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--ink-60)', marginBottom: '1.25rem', lineHeight: '1.5' }}>
              This will remove the deploy link for <strong style={{ color: 'var(--accent-bright)' }}>{undeployTarget.name}</strong>.
              Users will no longer be able to access this bot via its link.
              To confirm, type <strong style={{ color: 'var(--ink-100)' }}>{undeployTarget.name}</strong> below.
            </p>
            <input
              className="glass-input"
              placeholder={`Type "${undeployTarget.name}" to confirm`}
              value={undeployConfirmText}
              onChange={(e) => setUndeployConfirmText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && isUndeployConfirmed) handleUndeploy();
              }}
              autoFocus
              style={{
                width: '100%',
                marginBottom: '1.25rem',
                borderColor: undeployConfirmText && !isUndeployConfirmed
                  ? 'rgba(16,185,129,0.4)'
                  : undefined,
              }}
            />
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
              <button
                className="action-btn"
                onClick={() => {
                  setUndeployTarget(null);
                  setUndeployConfirmText('');
                }}
                style={{ fontSize: '12px', padding: '8px 16px' }}
              >
                Cancel
              </button>
              <button
                className="action-btn"
                disabled={!isUndeployConfirmed}
                onClick={handleUndeploy}
                style={{
                  fontSize: '12px',
                  padding: '8px 20px',
                  background: isUndeployConfirmed ? 'rgba(16,185,129,0.15)' : 'transparent',
                  borderColor: isUndeployConfirmed ? 'rgba(16,185,129,0.5)' : 'rgba(255,255,255,0.08)',
                  color: isUndeployConfirmed ? 'var(--accent-bright)' : 'var(--ink-35)',
                  cursor: isUndeployConfirmed ? 'pointer' : 'not-allowed',
                  opacity: isUndeployConfirmed ? 1 : 0.5,
                }}
              >
                Undeploy
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
