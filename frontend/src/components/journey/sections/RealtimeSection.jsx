import { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';

const REALTIME_TYPES = [
  { value: 'livekit', label: 'LiveKit Realtime', serverUrl: 'ws://localhost:7880', desc: 'Local Docker container or LiveKit Cloud' },
  { value: 'custom_livekit', label: 'Custom / Enterprise LiveKit', serverUrl: '', desc: 'Self-hosted LiveKit cluster' },
];

/**
 * RealtimeSection — Glass pane for Realtime Transport Provider configuration.
 * 100% matches LLMSection structure, typography, CSS classes, inputs, and connector logic.
 */
export function RealtimeSection({ onProviderCreated }) {
  const [providers, setProviders] = useState([]);
  const [editingProviderId, setEditingProviderId] = useState(null);
  const [form, setForm] = useState({
    name: '',
    provider_type: 'livekit',
    server_url: 'ws://localhost:7880',
    api_key: '',
    api_secret: '',
    room_token_ttl_seconds: 3600,
    audio_sample_rate: 16000,
  });

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [testingConnection, setTestingConnection] = useState(false);
  const [connectionValid, setConnectionValid] = useState(false);

  // Deletion modal state
  const [deletingProviderId, setDeletingProviderId] = useState(null);

  const fetchProvidersList = useCallback(() => {
    fetch('/admin/api/realtime-runtime')
      .then((r) => r.json())
      .then((data) => setProviders(Array.isArray(data) ? data : []))
      .catch(() => setProviders([]));
  }, []);

  useEffect(() => {
    fetchProvidersList();
  }, [fetchProvidersList]);

  // Connection verification
  const testConnection = useCallback(async (overrideServerUrl, overrideApiKey, overrideApiSecret, providerId = null) => {
    const url = overrideServerUrl !== undefined ? overrideServerUrl : form.server_url;
    const key = overrideApiKey !== undefined ? overrideApiKey : form.api_key;
    const secret = overrideApiSecret !== undefined ? overrideApiSecret : form.api_secret;

    if (!url && !providerId) return;

    setTestingConnection(true);
    setTestResult(null);

    try {
      const bodyPayload = providerId && (!key || !secret)
        ? { config_id: providerId, server_url: url }
        : { server_url: url, api_key: key, api_secret: secret, config_id: providerId };

      const res = await fetch('/admin/api/realtime-runtime/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(bodyPayload),
      });
      const data = await res.json();
      if (res.ok && data?.ok) {
        setConnectionValid(true);
        setTestResult({ success: true, message: data.message || `Successfully connected to ${url}!` });
      } else {
        if (!providerId) setConnectionValid(false);
        setTestResult({ success: false, message: data.error || 'Could not connect to transport server. Verify URL and credentials.' });
      }
    } catch (err) {
      if (!providerId) setConnectionValid(false);
      setTestResult({ success: false, message: `Connection error: ${err.message}` });
    }
    setTestingConnection(false);
  }, [form.server_url, form.api_key, form.api_secret]);

  const handleSelectForEdit = async (provider) => {
    setEditingProviderId(provider.id);
    setForm({
      name: provider.name || '',
      provider_type: provider.provider_type || 'livekit',
      server_url: provider.server_url || '',
      api_key: '',
      api_secret: '',
      room_token_ttl_seconds: provider.room_token_ttl_seconds || 3600,
      audio_sample_rate: provider.audio_sample_rate || 16000,
    });
    setConnectionValid(true);
    setTestResult({ success: true, message: `Editing "${provider.name}". Change any field below and click Update Provider.` });
  };

  const resetFormToNew = () => {
    setEditingProviderId(null);
    setForm({
      name: '',
      provider_type: 'livekit',
      server_url: 'ws://localhost:7880',
      api_key: '',
      api_secret: '',
      room_token_ttl_seconds: 3600,
      audio_sample_rate: 16000,
    });
    setConnectionValid(false);
    setTestResult(null);
  };

  const handleTypeChange = (e) => {
    const typeVal = e.target.value;
    const typeObj = REALTIME_TYPES.find((t) => t.value === typeVal);
    setForm((f) => ({
      ...f,
      provider_type: typeVal,
      server_url: typeObj?.serverUrl || f.server_url,
    }));
    setConnectionValid(false);
    setTestResult(null);
  };

  const handleSave = async (e) => {
    if (e) e.preventDefault();
    if (!form.name.trim() || !form.server_url.trim()) return;

    setTesting(true);
    try {
      const endpoint = editingProviderId
        ? `/admin/api/realtime-runtime/${editingProviderId}`
        : '/admin/api/realtime-runtime';
      const method = editingProviderId ? 'PUT' : 'POST';

      const payload = {
        name: form.name.trim(),
        provider_type: form.provider_type,
        server_url: form.server_url.trim(),
        room_token_ttl_seconds: Number(form.room_token_ttl_seconds),
        audio_sample_rate: Number(form.audio_sample_rate),
        ...(form.api_key.trim() ? { api_key: form.api_key.trim() } : {}),
        ...(form.api_secret.trim() ? { api_secret: form.api_secret.trim() } : {}),
      };

      const res = await fetch(endpoint, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (res.ok) {
        setTestResult({
          success: true,
          message: editingProviderId ? 'Transport provider updated successfully!' : 'Transport provider created & saved successfully!',
        });
        resetFormToNew();
        fetchProvidersList();
        onProviderCreated?.(data);
      } else {
        setTestResult({ success: false, message: data.detail || 'Save failed' });
      }
    } catch (err) {
      setTestResult({ success: false, message: err.message });
    }
    setTesting(false);
  };

  const confirmDelete = async () => {
    if (!deletingProviderId) return;
    await fetch(`/admin/api/realtime-runtime/${deletingProviderId}`, { method: 'DELETE' });
    setProviders((prev) => prev.filter((p) => p.id !== deletingProviderId));
    if (editingProviderId === deletingProviderId) {
      resetFormToNew();
    }
    setDeletingProviderId(null);
  };

  const isFormValid = editingProviderId
    ? form.name.trim() !== '' && form.server_url.trim() !== ''
    : form.name.trim() !== '' && form.server_url.trim() !== '' && form.api_key.trim() !== '' && form.api_secret.trim() !== '';

  return (
    <div className="journey-section journey-section--split">
      <div className="journey-section__content">
        {/* Step indicator dot matching LLMSection */}
        <div className="step-indicator">
          <span className="step-indicator__dot" />
          Step 2 of 5
        </div>

        <h2 className="type-display type-display-lg" style={{ marginBottom: '0.75rem' }}>
          Realtime Transport
        </h2>
        <p className="type-body" style={{ marginBottom: '1.5rem', maxWidth: '520px' }}>
          Connect realtime voice transport providers (local Docker container, cloud cluster). Click any configured provider to view or edit its settings.
        </p>

        {/* Existing providers list */}
        {providers.length > 0 && (
          <div className="glass-pane" style={{ marginBottom: '1.5rem', padding: '1rem 1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <span className="type-micro">Connected Transport Providers (Click to Edit)</span>
              {editingProviderId && (
                <button
                  type="button"
                  onClick={resetFormToNew}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--accent-bright)',
                    fontSize: '11px',
                    cursor: 'pointer',
                    fontWeight: 500,
                  }}
                >
                  + Create New Transport
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
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '12px 14px',
                    marginBottom: '6px',
                    background: isSelected ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.02)',
                    border: `1px solid ${isSelected ? 'var(--accent-mid)' : 'rgba(255,255,255,0.06)'}`,
                    borderRadius: '8px',
                    cursor: 'pointer',
                    transition: 'all 200ms cubic-bezier(0.16, 1, 0.3, 1)',
                    boxShadow: isSelected ? '0 0 16px rgba(0,0,0,0.5), 0 0 10px hsla(275, 60%, 40%, 0.2)' : 'none',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <span
                      style={{
                        width: '6px',
                        height: '6px',
                        borderRadius: '50%',
                        background: isSelected ? 'var(--accent-bright)' : 'var(--ink-35)',
                        boxShadow: isSelected ? '0 0 6px var(--accent-bright)' : 'none',
                      }}
                    />
                    <div>
                      <div style={{ color: isSelected ? 'var(--accent-bright)' : 'var(--ink-100)', fontSize: '14px', fontWeight: 500 }}>
                        {p.name} {p.is_active && <span style={{ fontSize: '10px', color: 'var(--accent-bright)', marginLeft: '6px' }}>[ACTIVE]</span>} {isSelected && <span style={{ fontSize: '11px', opacity: 0.8 }}>(Editing)</span>}
                      </div>
                      <div className="type-micro" style={{ fontSize: '10px', marginTop: '2px' }}>
                        {p.provider_type?.toUpperCase()} • {p.server_url}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSelectForEdit(p);
                      }}
                      style={{
                        background: 'rgba(255,255,255,0.05)',
                        border: '1px solid rgba(255,255,255,0.12)',
                        color: 'var(--ink-90)',
                        fontSize: '11px',
                        padding: '4px 10px',
                        borderRadius: '4px',
                        cursor: 'pointer',
                      }}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeletingProviderId(p.id);
                      }}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--ink-35)',
                        fontSize: '12px',
                        cursor: 'pointer',
                        transition: 'color 200ms',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--warn)')}
                      onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--ink-35)')}
                    >
                      Remove
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Configuration pane */}
        <div className="glass-pane">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <span className="type-micro">
              {editingProviderId ? `Edit "${form.name}" Transport` : 'Add New Transport Provider'}
            </span>
            {editingProviderId && (
              <button
                type="button"
                onClick={resetFormToNew}
                style={{ background: 'none', border: 'none', color: 'var(--ink-60)', fontSize: '11px', cursor: 'pointer' }}
              >
                Cancel Editing
              </button>
            )}
          </div>

          <div style={{ display: 'grid', gap: '1rem' }}>
            <div>
              <label className="type-micro" style={{ display: 'block', marginBottom: '4px' }}>
                Provider Name *
              </label>
              <input
                className="glass-input"
                placeholder="Provider name (e.g. Local Docker, Production Cloud)"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>

            <div>
              <label className="type-micro" style={{ display: 'block', marginBottom: '4px' }}>
                Provider Type *
              </label>
              <select
                className="glass-input glass-select"
                value={form.provider_type}
                onChange={handleTypeChange}
              >
                {REALTIME_TYPES.map((t) => (
                  <option key={t.value} value={t.value} style={{ background: '#111' }}>
                    {t.label} ({t.desc})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="type-micro" style={{ display: 'block', marginBottom: '4px' }}>
                Server URL *
              </label>
              <input
                className="glass-input"
                placeholder="ws://localhost:7880 or wss://your-cluster.livekit.cloud"
                value={form.server_url}
                onChange={(e) => {
                  const url = e.target.value;
                  setForm({ ...form, server_url: url });
                  setConnectionValid(false);
                  setTestResult(null);
                }}
              />
              <div style={{ fontSize: '11px', color: 'var(--ink-35)', marginTop: '4px' }}>
                Use <code>ws://localhost:7880</code> for local Docker or <code>wss://...</code> for cloud clusters.
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <label className="type-micro" style={{ display: 'block', marginBottom: '4px' }}>
                  API Key {editingProviderId ? '(Leave blank to keep saved)' : '*'}
                </label>
                <input
                  className="glass-input"
                  type="password"
                  placeholder={editingProviderId ? '•••••••• (Saved - enter new key to update)' : 'API Key'}
                  value={form.api_key}
                  onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                />
              </div>
              <div>
                <label className="type-micro" style={{ display: 'block', marginBottom: '4px' }}>
                  API Secret {editingProviderId ? '(Leave blank to keep saved)' : '*'}
                </label>
                <input
                  className="glass-input"
                  type="password"
                  placeholder={editingProviderId ? '•••••••• (Saved - enter new secret to update)' : 'API Secret'}
                  value={form.api_secret}
                  onChange={(e) => setForm({ ...form, api_secret: e.target.value })}
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <label className="type-micro" style={{ display: 'block', marginBottom: '4px' }}>
                  Token TTL (Seconds)
                </label>
                <input
                  className="glass-input"
                  type="number"
                  value={form.room_token_ttl_seconds}
                  onChange={(e) => setForm({ ...form, room_token_ttl_seconds: e.target.value })}
                />
              </div>
              <div>
                <label className="type-micro" style={{ display: 'block', marginBottom: '4px' }}>
                  Audio Sample Rate (Hz)
                </label>
                <input
                  className="glass-input"
                  type="number"
                  value={form.audio_sample_rate}
                  onChange={(e) => setForm({ ...form, audio_sample_rate: e.target.value })}
                />
              </div>
            </div>

            {testingConnection && (
              <p style={{ fontSize: '12px', color: 'var(--ink-60)', margin: 0 }}>
                ⏳ Verifying transport server endpoint connection...
              </p>
            )}

            {testResult && (
              <p style={{ fontSize: '13px', margin: 0, color: testResult.success ? 'var(--accent-bright)' : 'var(--warn)' }}>
                {testResult.success ? '✓ ' : '✗ '}{testResult.message}
              </p>
            )}

            <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem' }}>
              <button
                type="button"
                className="action-btn"
                onClick={() => testConnection(form.server_url, form.api_key, form.api_secret, editingProviderId)}
                disabled={testingConnection || (!form.server_url && !editingProviderId)}
                style={{ flex: '0 0 auto' }}
              >
                {testingConnection ? 'Testing...' : 'Test Connection'}
              </button>

              <button
                type="button"
                className={`action-btn ${isFormValid ? 'action-btn--primary' : ''}`}
                onClick={handleSave}
                disabled={testing || !isFormValid}
                style={{
                  flex: 1,
                  opacity: isFormValid ? 1 : 0.4,
                  cursor: isFormValid ? 'pointer' : 'not-allowed',
                }}
              >
                {testing && <span className="loading-ring" />}
                {testing ? 'Saving...' : editingProviderId ? 'Update Provider' : 'Save Transport Provider'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Delete Confirmation Modal — rendered in document.body for exact viewport centering */}
      {deletingProviderId && createPortal(
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
        >
          <div
            className="glass-pane"
            style={{
              width: '90%',
              maxWidth: '420px',
              padding: '2rem',
              textAlign: 'center',
              border: '1px solid rgba(255,255,255,0.18)',
              boxShadow: '0 0 50px rgba(0,0,0,0.9), 0 0 20px rgba(255,255,255,0.05)',
            }}
          >
            <h3 style={{ fontFamily: 'var(--font-display)', color: 'var(--ink-100)', marginBottom: '0.75rem' }}>
              Confirm Deletion
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--ink-60)', marginBottom: '1.5rem' }}>
              Are you sure you want to remove this transport provider? New voice sessions will no longer be able to use it.
            </p>
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
              <button
                onClick={() => setDeletingProviderId(null)}
                style={{
                  padding: '8px 18px',
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(255,255,255,0.15)',
                  color: 'var(--ink-100)',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '12px',
                }}
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                style={{
                  padding: '8px 18px',
                  background: 'var(--warn)',
                  border: 'none',
                  color: '#fff',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '12px',
                  fontWeight: 500,
                }}
              >
                Delete Provider
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* Sidebar hints */}
      <div className="journey-section__sidebar">
        <div className="section-hint">
          <div className="section-hint__title">WebRTC Transport</div>
          <div className="section-hint__body">
            Realtime transport handles sub-100ms ultra-low latency WebRTC audio channels between browser and agent.
          </div>
        </div>

        <div className="section-hint">
          <div className="section-hint__title">Local & Cloud</div>
          <div className="section-hint__body">
            Switch seamlessly between local Docker (ws://localhost:7880) and production LiveKit Cloud clusters.
          </div>
        </div>

        <div className="section-hint">
          <div className="section-hint__title">Zero Hardcoding</div>
          <div className="section-hint__body">
            Transport credentials are stored in PostgreSQL using AES-256-GCM envelope encryption.
          </div>
        </div>
      </div>
    </div>
  );
}
