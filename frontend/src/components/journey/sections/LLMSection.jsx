import { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';

const LLM_TYPES = [
  { value: 'openai', label: 'OpenAI', baseUrl: 'https://api.openai.com/v1', desc: 'GPT-4o, GPT-4o-mini, o1' },
  { value: 'anthropic', label: 'Anthropic', baseUrl: 'https://api.anthropic.com', desc: 'Claude 3.5 Sonnet, Haiku' },
  { value: 'google', label: 'Google', baseUrl: '', desc: 'Gemini 2.0, 1.5 Pro' },
  { value: 'mistral', label: 'Mistral', baseUrl: 'https://api.mistral.ai/v1', desc: 'Mistral Large, Small' },
  { value: 'moonshot', label: 'Moonshot', baseUrl: 'https://api.moonshot.cn/v1', desc: 'Kimi models' },
  { value: 'ollama', label: 'Ollama', baseUrl: 'http://localhost:11434/v1', desc: 'Local models (Llama, etc.)' },
  { value: 'openrouter', label: 'OpenRouter', baseUrl: 'https://openrouter.ai/api/v1', desc: 'Multi-provider gateway' },
  { value: 'azure_openai', label: 'Azure OpenAI', baseUrl: '', desc: 'Enterprise Azure deployment' },
  { value: 'openai_compatible', label: 'Custom / OpenAI-Compatible', baseUrl: '', desc: 'Any OpenAI-compatible API' },
];

/**
 * LLMSection — Glass pane for LLM provider configuration.
 * - Connects & configures LLM providers (Base URL, Provider Type, API Key).
 * - Clicking any connected provider opens its configuration for editing.
 * - Models are configured inside Bot Identity (Step 3) when assigning models to a bot.
 */
export function LLMSection({ onProviderCreated }) {
  const [providers, setProviders] = useState([]);
  const [editingProviderId, setEditingProviderId] = useState(null);
  const [deployedProviderIds, setDeployedProviderIds] = useState(new Set());
  const [form, setForm] = useState({
    name: '',
    provider_type: 'openai',
    base_url: 'https://api.openai.com/v1',
    credentials: { api_key: '' },
  });

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [testingConnection, setTestingConnection] = useState(false);
  const [connectionValid, setConnectionValid] = useState(false);

  // Deletion modal state
  const [deletingProviderId, setDeletingProviderId] = useState(null);
  const [deployedBotWarning, setDeployedBotWarning] = useState(null); // { providerId, botNames }
  const [showAllProviders, setShowAllProviders] = useState(false);
  const formRef = useRef(null);
  const PROVIDERS_VISIBLE = 3;

  const fetchProvidersList = useCallback(() => {
    fetch('/admin/api/llm-providers')
      .then((r) => r.json())
      .then((data) => setProviders(data || []))
      .catch(() => {});
    // Track which providers are used by deployed bots
    fetch('/admin/api/bots')
      .then((r) => r.json())
      .then((bots) => {
        const ids = new Set((bots || []).filter(b => b.is_deployed && b.llm_provider_id).map(b => b.llm_provider_id));
        setDeployedProviderIds(ids);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchProvidersList();
  }, [fetchProvidersList]);

  // Automatic connection verification
  const autoTestAndFetchModels = useCallback(async (baseUrl, apiKey, providerType, providerId = null) => {
    const url = baseUrl !== undefined ? baseUrl : form.base_url;
    const key = apiKey !== undefined ? apiKey : form.credentials.api_key;
    const type = providerType !== undefined ? providerType : form.provider_type;

    if (!url && !providerId) return;

    setTestingConnection(true);
    try {
      const bodyPayload = providerId && !key
        ? { provider_id: providerId, base_url: url, provider_type: type }
        : { base_url: url, api_key: key, provider_type: type };

      const res = await fetch('/admin/api/llm-providers/fetch-models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(bodyPayload),
      });
      const data = await res.json();
      if (res.ok && data?.models) {
        setConnectionValid(true);
        setTestResult({ success: true, message: `Connected! Discovered ${data.models?.length || 0} models dynamically.` });
      } else {
        if (!providerId) setConnectionValid(false);
        setTestResult({ success: false, message: 'Could not connect to provider. Verify base URL and API key.' });
      }
    } catch (err) {
      if (!providerId) setConnectionValid(false);
      setTestResult({ success: false, message: `Connection error: ${err.message}` });
    }
    setTestingConnection(false);
  }, [form.base_url, form.credentials.api_key, form.provider_type]);

  const handleSelectForEdit = async (provider) => {
    setEditingProviderId(provider.id);
    setForm({
      name: provider.name || '',
      provider_type: provider.provider_type || 'openai',
      base_url: provider.base_url || '',
      credentials: { api_key: '' }, // empty means keep saved encrypted key
    });
    setConnectionValid(true); // Existing configured provider is valid by default
    setTestResult({ success: true, message: `Editing "${provider.name}". Change any field below and click Update.` });

    // Verify connection using saved provider credentials in background
    autoTestAndFetchModels(provider.base_url, '', provider.provider_type, provider.id);
  };

  const resetFormToNew = () => {
    setEditingProviderId(null);
    const preset = LLM_TYPES.find((t) => t.value === 'openai');
    setForm({
      name: '',
      provider_type: 'openai',
      base_url: preset?.baseUrl || 'https://api.openai.com/v1',
      credentials: { api_key: '' },
    });
    setConnectionValid(false);
    setTestResult(null);
  };

  const handleTypeChange = (e) => {
    const type = e.target.value;
    const preset = LLM_TYPES.find((t) => t.value === type);
    const newBaseUrl = preset?.baseUrl || '';
    setForm((prev) => ({ ...prev, provider_type: type, base_url: newBaseUrl }));
    autoTestAndFetchModels(newBaseUrl, form.credentials.api_key, type, editingProviderId);
  };

  const handleSave = async () => {
    if (!form.name || !form.base_url) return;

    setTesting(true);
    setTestResult(null);
    try {
      const endpoint = editingProviderId
        ? `/admin/api/llm-providers/${editingProviderId}`
        : '/admin/api/llm-providers';
      const method = editingProviderId ? 'PUT' : 'POST';

      const payload = {
        name: form.name,
        provider_type: form.provider_type,
        base_url: form.base_url,
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
        setTestResult({
          success: true,
          message: editingProviderId ? 'Provider updated successfully!' : 'Provider created & saved successfully!',
        });
        resetFormToNew();
        onProviderCreated?.(data);
        fetchProvidersList();
      } else {
        setTestResult({ success: false, message: data.detail || 'Save failed' });
      }
    } catch (err) {
      setTestResult({ success: false, message: err.message });
    }
    setTesting(false);
  };

  const handleRemoveClick = async (providerId) => {
    // Check if any deployed bot uses this provider before showing confirmation
    try {
      const res = await fetch('/admin/api/bots');
      const bots = await res.json();
      const usingBots = (bots || []).filter(b => b.is_deployed && b.llm_provider_id === providerId);
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
      const res = await fetch(`/admin/api/llm-providers/${deletingProviderId}`, { method: 'DELETE' });
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
    ? form.name.trim() !== '' && form.base_url.trim() !== ''
    : form.name.trim() !== '' && form.base_url.trim() !== '' && form.credentials.api_key.trim() !== '' && connectionValid;

  return (
    <div className="journey-section journey-section--split">
      <div className="journey-section__content">
        <div className="step-indicator">
          <span className="step-indicator__dot" />
          Step 1 of 4
        </div>

        <h2 className="type-display type-display-lg" style={{ marginBottom: '0.75rem' }}>
          Language Model
        </h2>
        <p className="type-body" style={{ marginBottom: '1.5rem', maxWidth: '520px' }}>
          Connect an LLM provider to power your bot's reasoning.
          Click any configured provider to view or edit its settings.
        </p>

        {/* Existing providers list */}
        {providers.length > 0 && (
          <div className="glass-pane" style={{ marginBottom: '1.5rem', padding: '1rem 1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <span className="type-micro">Connected Providers ({providers.length})</span>
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
                        {p.provider_type} • {p.base_url}
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
                      onClick={(e) => { e.stopPropagation(); handleRemoveClick(p.id); }}
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

        {/* Configuration pane */}
        <div className="glass-pane" ref={formRef}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <span className="type-micro">
              {editingProviderId ? `Edit "${form.name}" Provider` : 'Add New LLM Provider'}
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
                placeholder="Provider name (e.g. My LLM Provider)"
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
                {LLM_TYPES.map((t) => (
                  <option key={t.value} value={t.value} style={{ background: '#111' }}>
                    {t.label} ({t.desc})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="type-micro" style={{ display: 'block', marginBottom: '4px' }}>
                Base API URL *
              </label>
              <input
                className="glass-input"
                placeholder="https://api.openai.com/v1"
                value={form.base_url}
                onChange={(e) => {
                  const url = e.target.value;
                  setForm({ ...form, base_url: url });
                  autoTestAndFetchModels(url, form.credentials.api_key, form.provider_type, editingProviderId);
                }}
              />
            </div>

            <div>
              <label className="type-micro" style={{ display: 'block', marginBottom: '4px' }}>
                API Key {editingProviderId ? '(Leave blank to keep saved key)' : '*'}
              </label>
              <input
                className="glass-input"
                type="password"
                placeholder={editingProviderId ? '•••••••••••••••• (Saved - enter new key to update)' : 'API Key'}
                value={form.credentials.api_key}
                onChange={(e) => {
                  const key = e.target.value;
                  setForm({ ...form, credentials: { api_key: key } });
                  autoTestAndFetchModels(form.base_url, key, form.provider_type, editingProviderId);
                }}
              />
            </div>

            {testingConnection && (
              <p style={{ fontSize: '12px', color: 'var(--ink-60)', margin: 0 }}>
                ⏳ Verifying API key & querying endpoint connection...
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
              disabled={testing || !isFormValid}
              style={{
                marginTop: '0.5rem',
                opacity: isFormValid ? 1 : 0.4,
                cursor: isFormValid ? 'pointer' : 'not-allowed',
              }}
            >
              {testing && <span className="loading-ring" />}
              {testing ? 'Saving...' : editingProviderId ? 'Update Provider' : 'Save Provider'}
            </button>
          </div>
        </div>
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
              Are you sure you want to remove this LLM provider? This action cannot be undone.
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
                  background: 'var(--accent-mid)',
                  border: 'none',
                  color: '#000',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '12px',
                  fontWeight: 600,
                }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
      <div className="journey-section__sidebar">
        <div className="section-hint">
          <div className="section-hint__title">LLM Reasoning</div>
          <div className="section-hint__body">
            Language models process user transcripts, maintain context, and decide conversational responses.
          </div>
        </div>

        <div className="section-hint">
          <div className="section-hint__title">Multi-Provider</div>
          <div className="section-hint__body">
            Configure OpenAI, Anthropic, Gemini, or custom OpenAI-compatible endpoints to power different bots.
          </div>
        </div>

        <div className="section-hint">
          <div className="section-hint__title">Model Discovery</div>
          <div className="section-hint__body">
            Entering your API Key dynamically discovers available models from the provider endpoint.
          </div>
        </div>
      </div>
    </div>
  );
}
