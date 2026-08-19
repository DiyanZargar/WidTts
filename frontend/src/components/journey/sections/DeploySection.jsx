import { useState, useEffect, useRef } from 'react';
import { GlassModal } from '../../common/GlassModal';

/**
 * DeploySection — Deploy bots with unique shareable links.
 * Each bot can be independently deployed, generating a URL like /bot/{slug}.
 * Deployed bots show their link with copy + open icon actions.
 * Undeploy requires typing the bot name to confirm (like GitHub repo deletion).
 */
export function DeploySection({ refreshTrigger, highlightBotId, onExtraPages }) {
  const [bots, setBots] = useState([]);
  const [deploying, setDeploying] = useState(null);
  const [copiedSlug, setCopiedSlug] = useState(null);
  const [showAllBots, setShowAllBots] = useState(false);
  const [highlightedId, setHighlightedId] = useState(null);
  const BOTS_VISIBLE = 3;
  const botRefs = useRef({});
  // Undeploy confirmation modal state
  const [undeployTarget, setUndeployTarget] = useState(null); // { id, name }
  const [undeployConfirmText, setUndeployConfirmText] = useState('');

  const load = () => {
    fetch('/admin/api/bots')
      .then((r) => r.json())
      .then((data) => {
        // Latest bots first
        setBots(Array.isArray(data) ? data.reverse() : []);
      })
      .catch(() => {});
  };

  useEffect(load, []);
  useEffect(() => {
    if (refreshTrigger) load();
  }, [refreshTrigger]);

  // When a bot is highlighted (navigated from BotIdentitySection),
  // auto-expand the list if the bot is hidden and flash it.
  useEffect(() => {
    if (!highlightBotId || bots.length === 0) return;
    const idx = bots.findIndex((b) => b.id === highlightBotId);
    if (idx === -1) return;
    if (idx >= BOTS_VISIBLE) setShowAllBots(true);
    setHighlightedId(highlightBotId);
    const clearTimer = setTimeout(() => setHighlightedId(null), 2500);
    return () => { clearTimeout(clearTimer); };
  }, [highlightBotId, bots]);

  // Notify parent when dropdown toggles so scroll pages can adjust
  useEffect(() => {
    if (!onExtraPages) return;
    if (showAllBots && bots.length > BOTS_VISIBLE) {
      const extraCards = bots.length - BOTS_VISIBLE;
      const extraPages = Math.ceil((extraCards * 80) / window.innerHeight);
      onExtraPages(extraPages);
    } else {
      onExtraPages(0);
    }
  }, [showAllBots, bots, onExtraPages]);

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

        <h2 className="type-display type-display-lg mb-3">
          Review & Deploy
        </h2>
        <p className="type-body mb-6 max-w-[520px]">
          Deploy your configured bots to generate shareable links.
          Each bot gets its own unique URL that users can access directly.
        </p>

        {bots.length === 0 ? (
          <div className="glass-pane text-center py-12 px-8">
            <p className="text-sm text-white/60 mb-2">No bots configured yet</p>
            <p className="type-micro">Create a bot in the previous step to see it here</p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {(showAllBots ? bots : bots.slice(0, BOTS_VISIBLE)).map((bot) => (
              <div
                key={bot.id}
                data-bot-id={bot.id}
                ref={(el) => { if (el) botRefs.current[bot.id] = el; }}
                className={`glass-pane p-4 transition-all duration-300 ${
                  deploying === bot.id ? 'flash-success' : ''
                } ${
                  highlightedId === bot.id
                    ? 'border-emerald-400 bg-emerald-500/10 shadow-[0_0_20px_rgba(16,185,129,0.3)]'
                    : bot.is_deployed
                    ? 'border-emerald-500/30 bg-white/[0.04]'
                    : ''
                }`}
              >
                {/* Top row: name + status + description + metadata + actions */}
                <div className="flex items-center gap-2.5 mb-2 flex-wrap">
                  <span
                    className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                      bot.is_deployed
                        ? 'bg-emerald-400 shadow-[0_0_6px_var(--accent-mid)]'
                        : 'bg-white/20'
                    }`}
                  />
                  <span
                    className={`font-display text-sm font-medium ${
                      bot.is_deployed ? 'text-emerald-400' : 'text-white'
                    }`}
                  >
                    {bot.name}
                  </span>
                  {bot.is_deployed && (
                    <span className="text-[8px] px-1.5 py-0.5 rounded bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 font-semibold">
                      DEPLOYED
                    </span>
                  )}
                  {bot.description && (
                    <span className="text-xs text-white/40 ml-1 truncate max-w-[200px]">
                      {bot.description}
                    </span>
                  )}
                  <span className="ml-auto flex gap-3 items-center">
                    {bot.llm_model && (
                      <span className="type-micro text-[9px]">MODEL: {bot.llm_model}</span>
                    )}
                    {bot.system_prompt && (
                      <span className="type-micro text-[9px]">
                        PROMPT: {bot.system_prompt.length} CHARS
                      </span>
                    )}
                  </span>
                </div>

                {/* Deploy link + actions — single compact row */}
                {bot.is_deployed && bot.deploy_slug && (
                  <div className="flex items-center gap-2 p-2 mt-1.5 bg-white/[0.04] border border-white/10 rounded-md">
                    <span className="flex-1 font-mono text-xs text-emerald-400 overflow-hidden text-ellipsis whitespace-nowrap">
                      {`${window.location.origin}/bot/${bot.deploy_slug}`}
                    </span>
                    <button
                      type="button"
                      onClick={() => handleCopyLink(bot.deploy_slug)}
                      title={copiedSlug === bot.deploy_slug ? 'Copied!' : 'Copy link'}
                      className={`p-1.5 rounded border border-white/10 bg-white/5 hover:border-emerald-400 hover:text-emerald-400 transition cursor-pointer ${
                        copiedSlug === bot.deploy_slug ? 'text-emerald-400 border-emerald-400' : 'text-white/60'
                      }`}
                    >
                      {copiedSlug === bot.deploy_slug ? (
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      ) : (
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                        </svg>
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleOpenLink(bot.deploy_slug)}
                      title="Open in new tab"
                      className="p-1.5 rounded border border-white/10 bg-white/5 text-white/60 hover:border-emerald-400 hover:text-emerald-400 transition cursor-pointer"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                        <polyline points="15 3 21 3 21 9" />
                        <line x1="10" y1="14" x2="21" y2="3" />
                      </svg>
                    </button>
                    <button
                      type="button"
                      className="action-btn text-[10px] py-1 px-2.5 border-white/10 text-white/40 hover:border-amber-500 hover:text-amber-500 transition"
                      onClick={() => {
                        setUndeployTarget({ id: bot.id, name: bot.name });
                        setUndeployConfirmText('');
                      }}
                    >
                      Undeploy
                    </button>
                  </div>
                )}

                {/* Deploy button for non-deployed bots */}
                {!bot.is_deployed && (
                  <div className="mt-2">
                    <button
                      type="button"
                      className="action-btn action-btn--primary text-xs py-1.5 px-4"
                      onClick={() => handleDeploy(bot.id)}
                      disabled={deploying === bot.id}
                    >
                      {deploying === bot.id ? 'Deploying...' : 'Deploy'}
                    </button>
                  </div>
                )}
              </div>
            ))}

            {bots.length > BOTS_VISIBLE && (
              <button
                type="button"
                onClick={() => setShowAllBots(!showAllBots)}
                className="w-full p-2 mt-1 border border-dashed border-white/10 rounded-md text-xs text-white/60 hover:text-emerald-400 hover:border-emerald-400/40 transition"
              >
                {showAllBots ? 'Show less' : `Show ${bots.length - BOTS_VISIBLE} more`}
              </button>
            )}
          </div>
        )}
      </div>

      {/* Sidebar hints */}
      <div className="journey-section__sidebar">
        <div className="section-hint">
          <div className="section-hint__title">Deployment</div>
          <div className="section-hint__body">
            Deploying a bot generates a unique shareable link. Users with this link can interact directly with that specific bot.
          </div>
        </div>

        <div className="section-hint">
          <div className="section-hint__title">Per-bot isolation</div>
          <div className="section-hint__body">
            Each deployed bot runs independently with its own configuration, system prompt, and LLM/speech providers.
          </div>
        </div>

        <div className="section-hint">
          <div className="section-hint__title">What's next</div>
          <div className="section-hint__body">
            Share the deploy link with your users. They'll land on a dedicated page for that bot and can start a voice session.
          </div>
        </div>
      </div>

      {/* Reusable Undeploy Confirmation Modal */}
      <GlassModal
        open={Boolean(undeployTarget)}
        title="Undeploy Bot"
        onClose={() => {
          setUndeployTarget(null);
          setUndeployConfirmText('');
        }}
        footer={
          <div className="flex gap-3 justify-end">
            <button
              type="button"
              className="action-btn text-xs py-1.5 px-4"
              onClick={() => {
                setUndeployTarget(null);
                setUndeployConfirmText('');
              }}
            >
              Cancel
            </button>
            <button
              type="button"
              className="action-btn action-btn--primary text-xs py-1.5 px-4 bg-amber-500 border-amber-500 text-black hover:bg-amber-400 disabled:opacity-40 disabled:cursor-not-allowed"
              onClick={handleUndeploy}
              disabled={!isUndeployConfirmed}
            >
              I understand, undeploy this bot
            </button>
          </div>
        }
      >
        <p className="text-sm text-white/70 mb-3">
          This will deactivate the shareable link for <strong className="text-white font-semibold">{undeployTarget?.name}</strong>. Anyone with the URL will no longer be able to connect.
        </p>
        <div className="mb-4">
          <label className="type-micro block mb-1.5 text-white/60">
            Type <span className="text-white font-semibold">{undeployTarget?.name}</span> to confirm:
          </label>
          <input
            className="glass-input text-xs"
            placeholder={undeployTarget?.name}
            value={undeployConfirmText}
            onChange={(e) => setUndeployConfirmText(e.target.value)}
            autoFocus
          />
        </div>
      </GlassModal>
    </div>
  );
}
