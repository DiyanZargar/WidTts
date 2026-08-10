import { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';

/**
 * SpeechSection — Configure speech provider credentials (API key only).
 * Model and language selection is handled per-bot in BotIdentitySection.
 */
export function SpeechSection({ onProviderCreated }) {
  const [providers, setProviders] = useState([]);
  const [editingProviderId, setEditingProviderId] = useState(null);
  const [selectedType, setSelectedType] = useState(null);
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

  const fetchProvidersList = useCallback(() => {
    fetch('/admin/api/speech-providers')
      .then((r) => r.json())
      .then((data) => setProviders(data || []))
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
      const data = await res.json();
      if (res.ok && data) {
        setConnectionValid(true);
        setTestResult({ success: true, message: `Connected to ${form.provider_type}! API key verified.` });
      } else {
        setConnectionValid(false);
        setTestResult({ success: false, message: data.detail || `Invalid API key for ${form.provider_type}.` });
      }
    } catch (err) {
      setConnectionValid(false);
      setTestResult({ success: false, message: `Connection error: ${err.message}` });
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
    setTestResult({ success: true, message: `Editing "${provider.name}". Enter a new API key to update.` });
    // Verify saved key still works
    testConnection('', provider.id);
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
              <span className="type-micro">Active Speech Providers (Click to Edit)</span>
              {editingProviderId && (
                <button onClick={resetFormToNew} style={{ background: 'none', border: 'none', color: 'var(--accent-bright)', fontSize: '11px', cursor: 'pointer', fontWeight: 500 }}>
                  + Create New Provider
                </button>
              )}
            </div>
            {providers.map((p) => {
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
                      </div>
                      <div className="type-micro" style={{ fontSize: '10px', marginTop: '2px' }}>
                        {p.provider_type}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <button type="button" onClick={(e) => { e.stopPropagation(); handleSelectForEdit(p); }} style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.12)', color: 'var(--ink-90)', fontSize: '11px', padding: '4px 10px', borderRadius: '4px', cursor: 'pointer' }}>Edit</button>
                    <button type="button" onClick={(e) => { e.stopPropagation(); setDeletingProviderId(p.id); }} style={{ background: 'none', border: 'none', color: 'var(--ink-35)', fontSize: '12px', cursor: 'pointer' }} onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--warn)')} onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--ink-35)')}>Remove</button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Provider selection buttons */}
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
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
                    if (key.trim().length > 10) {
                      testConnection(key, null);
                    } else {
                      setConnectionValid(false);
                      setTestResult(null);
                    }
                  }}
                />
              </div>

              {testing && (
                <p style={{ fontSize: '12px', color: 'var(--ink-60)', margin: 0 }}>
                  ⏳ Verifying API key...
                </p>
              )}

              {testResult && (
                <p style={{ fontSize: '13px', margin: 0, color: testResult.success ? 'var(--accent-bright)' : 'var(--warn)' }}>
                  {testResult.success ? '✓ ' : '✗ '}{testResult.message}
                </p>
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
