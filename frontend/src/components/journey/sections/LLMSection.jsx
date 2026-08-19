import { useState, useEffect, useCallback, useRef } from 'react';
import { ConfigCardList } from '../../common/ConfigCardList';
import { GlassModal } from '../../common/GlassModal';

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
  const [, setDeployedProviderIds] = useState(new Set());
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
  const formRef = useRef(null);

  const fetchProvidersList = useCallback(() => {
    fetch('/admin/api/llm-providers')
      .then((r) => r.json())
      .then((data) => setProviders(data || []))
      .catch(() => {});
    // Track which providers are used by deployed bots
    fetch('/admin/api/bots')
      .then((r) => r.json())
      .then((bots) => {
        const ids = new Set((bots || []).filter((b) => b.is_deployed && b.llm_provider_id).map((b) => b.llm_provider_id));
        setDeployedProviderIds(ids);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchProvidersList();
  }, [fetchProvidersList]);

  // Automatic connection verification
  const verifyTimerRef = useRef(null);
  const autoTestAndFetchModels = useCallback(async (baseUrl, apiKey, providerType, providerId = null) => {
    const url = baseUrl !== undefined ? baseUrl : form.base_url;
    const key = apiKey !== undefined ? apiKey : form.credentials.api_key;
    const type = providerType !== undefined ? providerType : form.provider_type;

    if (!url && !providerId) return;

    setTestingConnection(true);
    setTestResult(null);
    try {
      const bodyPayload = providerId && !key
        ? { provider_id: providerId, base_url: url, provider_type: type }
        : { base_url: url, api_key: key, provider_type: type };

      const res = await fetch('/admin/api/llm-providers/fetch-models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(bodyPayload),
      });
      let data;
      try { data = await res.json(); } catch { data = null; }
      if (res.ok && data?.models) {
        setConnectionValid(true);
        setTestResult({ success: true, message: `Connected — ${data.models.length} models discovered` });
      } else {
        if (!providerId) setConnectionValid(false);
        const detail = data?.detail || data?.error;
        setTestResult({ success: false, message: detail || 'Could not verify. Check your base URL and API key.' });
      }
    } catch {
      if (!providerId) setConnectionValid(false);
      setTestResult({ success: false, message: 'Connection failed. Check your base URL and try again.' });
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
    setTestResult({ success: true, message: `Editing "${provider.name}". Enter your API key and click Test to verify.` });
    setTimeout(() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
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
    try {
      const res = await fetch('/admin/api/bots');
      const bots = await res.json();
      const usingBots = (bots || []).filter((b) => b.is_deployed && b.llm_provider_id === providerId);
      if (usingBots.length > 0) {
        setDeployedBotWarning({ providerId, botNames: usingBots.map((b) => b.name) });
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

        <h2 className="type-display type-display-lg mb-3">
          Language Model
        </h2>
        <p className="type-body mb-6 max-w-[520px]">
          Connect an LLM provider to power your bot's reasoning.
          Click any configured provider to view or edit its settings.
        </p>

        {/* Reusable Configured Providers List */}
        <ConfigCardList
          title="Connected Providers"
          count={providers.length}
          items={providers}
          selectedId={editingProviderId}
          onSelect={handleSelectForEdit}
          onRemove={handleRemoveClick}
          onAddNew={() => {
            resetFormToNew();
            setTimeout(() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
          }}
          addNewLabel="Add Provider"
          renderSubtitle={(p) => `${p.provider_type} • ${p.base_url}`}
        />

        {/* Configuration pane */}
        <div className="glass-pane" ref={formRef}>
          <div className="flex justify-between items-center mb-4">
            <span className="type-micro">
              {editingProviderId ? `Edit "${form.name}" Provider` : 'Add New LLM Provider'}
            </span>
            {editingProviderId && (
              <button
                type="button"
                onClick={resetFormToNew}
                className="text-xs text-white/60 hover:text-white transition cursor-pointer"
              >
                Cancel Editing
              </button>
            )}
          </div>

          <div className="grid gap-4">
            <div>
              <label className="type-micro block mb-1">
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
              <label className="type-micro block mb-1">
                Provider Type *
              </label>
              <select
                className="glass-input glass-select cursor-pointer"
                value={form.provider_type}
                onChange={handleTypeChange}
              >
                {LLM_TYPES.map((t) => (
                  <option key={t.value} value={t.value} className="bg-[#111113] text-white">
                    {t.label} ({t.desc})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="type-micro block mb-1">
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
              <label className="type-micro block mb-1">
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
                  clearTimeout(verifyTimerRef.current);
                  if (key.trim()) {
                    verifyTimerRef.current = setTimeout(() => {
                      autoTestAndFetchModels(form.base_url, key, form.provider_type, editingProviderId);
                    }, 600);
                  } else {
                    setTestResult(null);
                    setConnectionValid(false);
                  }
                }}
              />
            </div>

            {testingConnection && (
              <div className="flex items-center gap-2 p-2.5 rounded-md bg-white/[0.03] border border-white/[0.06]">
                <span className="w-1.5 h-1.5 rounded-full bg-white/35 animate-pulse" />
                <span className="text-xs text-white/60">
                  Verifying connection...
                </span>
              </div>
            )}

            {testResult && (
              <div
                className={`flex items-center gap-2 p-2.5 rounded-md border ${
                  testResult.success
                    ? 'bg-emerald-500/[0.06] border-emerald-500/20 text-emerald-400'
                    : 'bg-amber-500/[0.06] border-amber-500/20 text-amber-400'
                }`}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                    testResult.success ? 'bg-emerald-400 shadow-[0_0_6px_var(--accent-mid)]' : 'bg-amber-400'
                  }`}
                />
                <span className="text-xs font-medium">
                  {testResult.message}
                </span>
              </div>
            )}

            <button
              type="button"
              className={`action-btn mt-2 ${isFormValid ? 'action-btn--primary' : ''}`}
              onClick={handleSave}
              disabled={testing || !isFormValid}
            >
              {testing && <span className="loading-ring" />}
              {testing ? 'Saving...' : editingProviderId ? 'Update Provider' : 'Save Provider'}
            </button>
          </div>
        </div>
      </div>

      {/* Reusable Cannot Delete Warning Modal */}
      <GlassModal
        open={Boolean(deployedBotWarning)}
        title="Cannot Delete Provider"
        onClose={() => setDeployedBotWarning(null)}
        footer={
          <button
            type="button"
            onClick={() => setDeployedBotWarning(null)}
            className="action-btn text-xs py-1.5 px-4"
          >
            Close
          </button>
        }
      >
        <p className="text-sm text-white/70 mb-3">
          This provider is currently used by deployed bot(s). Undeploy them first before deleting.
        </p>
        {deployedBotWarning?.botNames && (
          <div className="p-3 rounded-lg bg-white/[0.03] border border-white/10 text-xs text-white/90">
            <div className="font-semibold text-emerald-400 mb-1.5">
              Used by {deployedBotWarning.botNames.length} {deployedBotWarning.botNames.length === 1 ? 'bot' : 'bots'}:
            </div>
            <ul className="list-disc pl-4 space-y-1">
              {deployedBotWarning.botNames.map((name, i) => (
                <li key={i}>{name}</li>
              ))}
            </ul>
          </div>
        )}
      </GlassModal>

      {/* Reusable Delete Confirmation Modal */}
      <GlassModal
        open={Boolean(deletingProviderId)}
        title="Confirm Deletion"
        onClose={() => setDeletingProviderId(null)}
        footer={
          <>
            <button
              type="button"
              onClick={() => setDeletingProviderId(null)}
              className="action-btn text-xs py-1.5 px-4"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={confirmDelete}
              className="action-btn action-btn--primary text-xs py-1.5 px-4 bg-amber-500 border-amber-500 text-black hover:bg-amber-400"
            >
              Delete
            </button>
          </>
        }
      >
        Are you sure you want to remove this LLM provider? This action cannot be undone.
      </GlassModal>

      {/* Sidebar Hints */}
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
