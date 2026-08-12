import { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';

/**
 * SpeechSection — Configure speech provider credentials (API key only).
 * Model and language selection is handled per-bot in BotIdentitySection.
 */
export function SpeechSection({ onProviderCreated }) {
  const [providers, setProviders] = useState([]);
  const [editingProviderId, setEditingProviderId] = useState(null);
  const [deployedProviderIds, setDeployedProviderIds] = useState(new Set());
  const [selectedType, setSelectedType] = useState(null);
  const verifyTimerRef = useRef(null);
  const [form, setForm] = useState({
    name: '',
    provider_type: 'deepgram',
    credentials: { api_key: '' },
  });

  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [connectionValid, setConnectionValid] = useState(false);
  const [testing, setTesting] = useState(false);

  // Deletion modal state
  const [deletingProviderId, setDeletingProviderId] = useState(null);
  const [deployedBotWarning, setDeployedBotWarning] = useState(null);
  const [showAllProviders, setShowAllProviders] = useState(false);
  const formRef = useRef(null);
  const PROVIDERS_VISIBLE = 3;

  const fetchProvidersList = useCallback(() => {
    fetch('/admin/api/speech-providers')
      .then((r) => r.json())
      .then((data) => setProviders(data || []))
      .catch(() => {});
    // Track which providers are used by deployed bots
    fetch('/admin/api/bots')
      .then((r) => r.json())
      .then((bots) => {
        const ids = new Set();
        (bots || []).filter(b => b.is_deployed).forEach(b => {
          if (b.stt_provider_id) ids.add(b.stt_provider_id);
          if (b.tts_provider_id) ids.add(b.tts_provider_id);
        });
        setDeployedProviderIds(ids);
      })
      .catch(() => {});
  }, []);

  useEffect(() => { fetchProvidersList(); }, [fetchProvidersList]);

  const testConnection = useCallback(async (key, providerId) => {
    if (!key && !providerId) return;
    setTesting(true);
    setTestResult(null);
    try {
      const body = providerId && !key
        ? { provider_id: providerId, provider_type: form.provider_type }
        : { provider_type: form.provider_type, api_key: key };
      const res = await fetch('/admin/api/speech-providers/fetch-models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      let data;
      try { data = await res.json(); } catch { data = null; }
      if (res.ok && data) {
        setConnectionValid(true);
        setTestResult({ success: true, message: `Connected — API key verified` });
      } else {
        setConnectionValid(false);
        const detail = data?.detail || data?.error;
        setTestResult({ success: false, message: detail || `Could not verify. Check your API key.` });
      }
    } catch {
      setConnectionValid(false);
      setTestResult({ success: false, message: 'Connection failed. Check your API key and try again.' });
    }
    setTesting(false);
  }, [form.provider_type]);

  const handleSelectForEdit = (provider) => {
    setEditingProviderId(provider.id);
    setSelectedType(provider.provider_type);
    setForm({
      name: provider.name || '',
      provider_type: provider.provider_type || 'deepgram',
      credentials: { api_key: '' },
    });
    setConnectionValid(true);
    setTestResult({ success: true, message: `Editing "${provider.name}". Enter your API key and click Test to verify.` });
  };

  const resetFormToNew = () => {
    setEditingProviderId(null);
    setSelectedType(null);
    setForm({
      name: '',
      provider_type: 'deepgram',
      credentials: { api_key: '' },
    });
    setTestResult(null);
    setConnectionValid(false);
  };

  const selectProvider = (type) => {
    setSelectedType(type);
    setForm((prev) => ({
      ...prev,
      provider_type: type,
      name: prev.name || (type === 'deepgram' ? 'Deepgram Speech' : type === 'elevenlabs' ? 'ElevenLabs Speech' : 'Fish Audio Speech'),
    }));
    setTestResult(null);
    setConnectionValid(false);
  };

  const handleSave = async () => {
    if (!isFormValid) return;
    setSaving(true);
    setTestResult(null);
    try {
      const endpoint = editingProviderId
        ? `/admin/api/speech-providers/${editingProviderId}`
        : '/admin/api/speech-providers';
      const method = editingProviderId ? 'PUT' : 'POST';

      const payload = {
        name: form.name,
        provider_type: form.provider_type,
      };
      if (form.credentials.api_key.trim() !== '') {
        payload.credentials = { api_key: form.credentials.api_key.trim() };
      }

      const res = await fetch(endpoint, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (res.ok) {
        const savedId = data.id || editingProviderId;
        setEditingProviderId(savedId);
        setConnectionValid(true);
        setForm((prev) => ({ ...prev, credentials: { api_key: '' } }));
        setTestResult({
          success: true,
          message: editingProviderId ? 'Provider updated!' : 'Provider saved!',
        });
        onProviderCreated?.(data);
        fetchProvidersList();
      } else {
        setTestResult({ success: false, message: data.detail || 'Failed to save' });
      }
    } catch (err) {
      setTestResult({ success: false, message: err.message });
    }
    setSaving(false);
  };

  const handleRemoveClick = async (providerId) => {
    try {
      const res = await fetch('/admin/api/bots');
      const bots = await res.json();
      const usingBots = (bots || []).filter(b => b.is_deployed && (b.stt_provider_id === providerId || b.tts_provider_id === providerId));
      if (usingBots.length > 0) {
        setDeployedBotWarning({ providerId, botNames: usingBots.map(b => b.name) });
        return;
      }
    } catch {
      // If check fails, fall through to normal confirmation
    }
    setDeletingProviderId(providerId);
  };

  const confirmDelete = async () => {
    if (!deletingProviderId) return;
    try {
      const res = await fetch(`/admin/api/speech-providers/${deletingProviderId}`, { method: 'DELETE' });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setTestResult({ success: false, message: data.detail || 'Cannot delete this provider.' });
        setDeletingProviderId(null);
        return;
      }
      setProviders((prev) => prev.filter((p) => p.id !== deletingProviderId));
      if (editingProviderId === deletingProviderId) resetFormToNew();
    } catch (err) {
      setTestResult({ success: false, message: err.message });
    }
    setDeletingProviderId(null);
  };

  const isFormValid = editingProviderId
    ? form.name.trim() !== ''
    : form.name.trim() !== '' && form.credentials.api_key.trim() !== '' && connectionValid;

  return (
    <div className="journey-section journey-section--split">
      <div className="journey-section__content">
        <div className="step-indicator">
          <span className="step-indicator__dot" />
          Step 2 of 4
        </div>

        <h2 className="type-display type-display-lg" style={{ marginBottom: '0.75rem' }}>
          Speech Engine
        </h2>
        <p className="type-body" style={{ marginBottom: '1.5rem', maxWidth: '520px' }}>
          Connect a speech provider by entering your API key. Model and language
          selection is configured per-bot in the Bot section.
        </p>

        {/* Existing providers list */}
        {providers.length > 0 && (
          <div className="glass-pane" style={{ marginBottom: '1.5rem', padding: '1rem 1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <span className="type-micro">Active Speech Providers ({providers.length})</span>
              <button
                onClick={() => { resetFormToNew(); setTimeout(() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100); }}
                style={{
                  background: 'var(--accent-bright)', border: 'none', color: '#000',
                  fontSize: '11px', padding: '5px 14px', borderRadius: '6px',
                  cursor: 'pointer', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px',
                  transition: 'opacity 200ms',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.85')}
                onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
              >
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                Add Provider
              </button>
            </div>
            {(showAllProviders ? providers : providers.slice(0, PROVIDERS_VISIBLE)).map((p) => {
              const isSelected = editingProviderId === p.id;
              return (
                <div
                  key={p.id}
                  onClick={() => handleSelectForEdit(p)}
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '12px 14px', marginBottom: '6px',
                    background: isSelected ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.02)',
                    border: `1px solid ${isSelected ? 'var(--accent-mid)' : 'rgba(255,255,255,0.06)'}`,
                    borderRadius: '8px', cursor: 'pointer', transition: 'all 200ms',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: isSelected ? 'var(--accent-bright)' : 'var(--ink-35)', boxShadow: isSelected ? '0 0 6px var(--accent-bright)' : 'none' }} />
                    <div>
                      <div style={{ color: isSelected ? 'var(--accent-bright)' : 'var(--ink-100)', fontSize: '14px', fontWeight: 500 }}>
                        {p.name} {isSelected && <span style={{ fontSize: '11px', opacity: 0.8 }}>(Editing)</span>}
                        {deployedProviderIds.has(p.id) && (
                          <span style={{
                            display: 'inline-flex', alignItems: 'center', gap: '3px',
                            marginLeft: '8px', padding: '1px 6px', fontSize: '8px', fontWeight: 600,
                            letterSpacing: '0.06em', borderRadius: '3px',
                            background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.25)',
                            color: 'var(--accent-bright)',
                          }}>
                            <span style={{ width: '4px', height: '4px', borderRadius: '50%', background: 'var(--accent-bright)' }} />
                            IN USE
                          </span>
                        )}
                      </div>
                      <div className="type-micro" style={{ fontSize: '10px', marginTop: '2px' }}>
                        {p.provider_type}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <button type="button" onClick={(e) => { e.stopPropagation(); handleSelectForEdit(p); }} style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.12)', color: 'var(--ink-90)', fontSize: '11px', padding: '4px 10px', borderRadius: '4px', cursor: 'pointer' }}>Edit</button>
                    <button type="button" onClick={(e) => { e.stopPropagation(); handleRemoveClick(p.id); }} style={{ background: 'none', border: 'none', color: 'var(--ink-35)', fontSize: '12px', cursor: 'pointer' }} onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--warn)')} onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--ink-35)')}>Remove</button>
                  </div>
                </div>
              );
            })}

            {providers.length > PROVIDERS_VISIBLE && (
              <button
                onClick={() => setShowAllProviders(!showAllProviders)}
                style={{
                  width: '100%', padding: '8px', marginTop: '4px',
                  background: 'none', border: '1px dashed rgba(255,255,255,0.1)',
                  borderRadius: '6px', color: 'var(--ink-60)', fontSize: '11px',
                  cursor: 'pointer', transition: 'color 200ms',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--accent-bright)')}
                onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--ink-60)')}
              >
                {showAllProviders ? 'Show less' : `Show ${providers.length - PROVIDERS_VISIBLE} more`}
              </button>
            )}
          </div>
        )}

        {/* Provider selection buttons */}
        <div ref={formRef} style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
          {['deepgram', 'elevenlabs', 'fishaudio'].map((type) => (
            <button
              key={type}
              onClick={() => selectProvider(type)}
              style={{
                flex: 1, padding: '1.5rem',
                background: selectedType === type ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.02)',
                border: `1px solid ${selectedType === type ? 'var(--accent-mid)' : 'rgba(255,255,255,0.08)'}`,
                borderRadius: '12px', cursor: 'pointer', transition: 'all 300ms',
                textAlign: 'center',
                transform: selectedType === type ? 'scale(1.02)' : 'scale(1)',
                boxShadow: selectedType === type ? '0 0 20px 2px hsla(275, 60%, 40%, 0.15)' : 'none',
              }}
            >
              <span style={{ display: 'block', fontFamily: 'var(--font-display)', fontSize: '16px', fontWeight: 400, color: selectedType === type ? 'var(--accent-bright)' : 'var(--ink-60)', marginBottom: '6px' }}>
                {type === 'deepgram' ? 'Deepgram' : type === 'elevenlabs' ? 'ElevenLabs' : 'Fish Audio'}
              </span>
              <span className="type-micro" style={{ fontSize: '10px' }}>
                {type === 'deepgram' ? 'Nova STT + Aura TTS' : type === 'elevenlabs' ? 'Scribe STT + Flash TTS' : 'TTS Only (83 Languages)'}
              </span>
            </button>
          ))}
        </div>

        {/* Configuration Pane — just name + API key */}
        {selectedType && (
          <div className="glass-pane">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <span className="type-micro">
                {editingProviderId ? `Edit "${form.name}"` : `Configure ${selectedType === 'deepgram' ? 'Deepgram' : selectedType === 'elevenlabs' ? 'ElevenLabs' : 'Fish Audio'}`}
              </span>
              {editingProviderId && (
                <button type="button" onClick={resetFormToNew} style={{ background: 'none', border: 'none', color: 'var(--ink-60)', fontSize: '11px', cursor: 'pointer' }}>
                  Cancel Editing
                </button>
              )}
            </div>

            <div style={{ display: 'grid', gap: '1rem' }}>
              <div>
                <label className="type-micro" style={{ display: 'block', marginBottom: '4px' }}>Provider Name *</label>
                <input className="glass-input" placeholder="Provider Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </div>

              <div>
                <label className="type-micro" style={{ display: 'block', marginBottom: '4px' }}>
                  API Key {editingProviderId ? '(Leave blank to keep saved key)' : '*'}
                </label>
                <input
                  className="glass-input"
                  type="password"
                  placeholder={editingProviderId ? '•••••••• (Saved — enter new key to update)' : 'API Key'}
                  value={form.credentials.api_key}
                  onChange={(e) => {
                    const key = e.target.value;
                    setForm({ ...form, credentials: { api_key: key } });
                    clearTimeout(verifyTimerRef.current);
                    if (key.trim()) {
                      verifyTimerRef.current = setTimeout(() => {
                        testConnection(key, null);
                      }, 600);
                    } else {
                      setConnectionValid(false);
                      setTestResult(null);
                    }
                  }}
                />
              </div>

              {testing && (
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '8px',
                  padding: '8px 12px', borderRadius: '6px',
                  background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
                }}>
                  <span style={{
                    width: '6px', height: '6px', borderRadius: '50%',
                    background: 'var(--ink-35)', animation: 'pulse 1.2s ease-in-out infinite',
                  }} />
                  <span style={{ fontSize: '11px', color: 'var(--ink-60)' }}>
                    Verifying connection...
                  </span>
                </div>
              )}

              {testResult && (
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '8px',
                  padding: '8px 12px', borderRadius: '6px',
                  background: testResult.success ? 'rgba(16,185,129,0.06)' : 'rgba(245,158,11,0.06)',
                  border: `1px solid ${testResult.success ? 'rgba(16,185,129,0.2)' : 'rgba(245,158,11,0.2)'}`,
                }}>
                  <span style={{
                    width: '6px', height: '6px', borderRadius: '50%', flexShrink: 0,
                    background: testResult.success ? 'var(--accent-bright)' : 'var(--warn)',
                    boxShadow: testResult.success ? '0 0 6px var(--accent-mid)' : '0 0 6px rgba(245,158,11,0.4)',
                  }} />
                  <span style={{
                    fontSize: '11px', fontWeight: 500,
                    color: testResult.success ? 'var(--accent-bright)' : 'var(--warn)',
                  }}>
                    {testResult.message}
                  </span>
                </div>
              )}

              <button
                className={`action-btn ${isFormValid ? 'action-btn--primary' : ''}`}
                onClick={handleSave}
                disabled={saving || !isFormValid}
                style={{ marginTop: '0.5rem', opacity: isFormValid ? 1 : 0.4, cursor: isFormValid ? 'pointer' : 'not-allowed' }}
              >
                {saving && <span className="loading-ring" />}
                {saving ? 'Saving...' : editingProviderId ? 'Update Provider' : 'Save Provider'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Cannot Delete Warning Modal — deployed bot uses this provider */}
      {deployedBotWarning && createPortal(
        <div
          style={{
            position: 'fixed', inset: 0,
            width: '100vw', height: '100vh',
            background: 'rgba(0,0,0,0.8)',
            backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)',
            display: 'grid', placeItems: 'center', zIndex: 99999,
          }}
        >
          <div
            className="glass-pane"
            style={{
              width: '90%', maxWidth: '420px', padding: '2rem',
              textAlign: 'center',
              border: '1px solid rgba(255,255,255,0.18)',
              boxShadow: '0 0 50px rgba(0,0,0,0.9), 0 0 20px rgba(255,255,255,0.05)',
            }}
          >
            <h3 style={{ fontFamily: 'var(--font-display)', color: 'var(--ink-100)', marginBottom: '0.75rem' }}>
              Cannot Delete
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--ink-60)', marginBottom: '1rem' }}>
              This provider is currently used by deployed bot(s). Undeploy them first before deleting.
            </p>
            <details style={{ marginBottom: '1.5rem', textAlign: 'center' }}>
              <summary style={{
                fontSize: '12px', color: 'var(--accent-bright)', cursor: 'pointer',
                display: 'inline-flex', alignItems: 'center', gap: '4px',
                listStyle: 'none', userSelect: 'none', justifyContent: 'center',
              }}>
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ transition: 'transform 200ms' }}>
                  <polyline points="6 9 12 15 18 9" />
                </svg>
                {deployedBotWarning.botNames.length} deployed {deployedBotWarning.botNames.length === 1 ? 'bot' : 'bots'}
              </summary>
              <div style={{ marginTop: '0.5rem' }}>
                {deployedBotWarning.botNames.map((name, i) => (
                  <div key={i} style={{
                    fontSize: '12px', color: 'var(--ink-90)', padding: '4px 0',
                    borderBottom: i < deployedBotWarning.botNames.length - 1 ? '1px solid rgba(255,255,255,0.06)' : 'none',
                  }}>
                    {name}
                  </div>
                ))}
              </div>
            </details>
            <button
              onClick={() => setDeployedBotWarning(null)}
              style={{
                padding: '8px 18px',
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.15)',
                color: 'var(--ink-100)', borderRadius: '6px',
                cursor: 'pointer', fontSize: '12px',
              }}
            >
              Close
            </button>
          </div>
        </div>,
        document.body
      )}

      {/* Delete Confirmation Modal */}
      {deletingProviderId && createPortal(
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(12px)', display: 'grid', placeItems: 'center', zIndex: 99999 }}>
          <div className="glass-pane" style={{ width: '90%', maxWidth: '420px', padding: '2rem', textAlign: 'center' }}>
            <h3 style={{ fontFamily: 'var(--font-display)', color: 'var(--ink-100)', marginBottom: '0.75rem' }}>Confirm Deletion</h3>
            <p style={{ fontSize: '13px', color: 'var(--ink-60)', marginBottom: '1.5rem' }}>Are you sure you want to remove this Speech provider? This action cannot be undone.</p>
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
              <button onClick={() => setDeletingProviderId(null)} style={{ padding: '8px 18px', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.15)', color: 'var(--ink-100)', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}>Cancel</button>
              <button onClick={confirmDelete} style={{ padding: '8px 18px', background: 'var(--accent-mid)', border: 'none', color: '#000', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: 600 }}>Delete</button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* Sidebar hints */}
      <div className="journey-section__sidebar">
        <div className="section-hint">
          <div className="section-hint__title">Speech Provider</div>
          <div className="section-hint__body">
            Connect your speech provider with an API key. Models and languages are selected per-bot in the Bot section.
          </div>
        </div>

        <div className="section-hint">
          <div className="section-hint__title">Supported Providers</div>
          <div className="section-hint__body">
            Deepgram (Nova STT, Aura TTS), ElevenLabs (Scribe STT, Flash TTS), and Fish Audio (TTS Only).
          </div>
        </div>

        <div className="section-hint">
          <div className="section-hint__title">Credentials Only</div>
          <div className="section-hint__body">
            This section stores your API key securely. All model and language configuration happens at the bot level.
          </div>
        </div>
      </div>
    </div>
  );
}
