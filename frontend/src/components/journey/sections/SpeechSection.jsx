import { useState, useEffect, useCallback, useRef } from 'react';
import { ConfigCardList } from '../../common/ConfigCardList';
import { GlassModal } from '../../common/GlassModal';

/**
 * SpeechSection — Configure speech provider credentials (API key only).
 * Model and language selection is handled per-bot in BotIdentitySection.
 */
export function SpeechSection({ onProviderCreated }) {
  const [providers, setProviders] = useState([]);
  const [editingProviderId, setEditingProviderId] = useState(null);
  const [, setDeployedProviderIds] = useState(new Set());
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
  const formRef = useRef(null);

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
        (bots || []).filter((b) => b.is_deployed).forEach((b) => {
          if (b.stt_provider_id) ids.add(b.stt_provider_id);
          if (b.tts_provider_id) ids.add(b.tts_provider_id);
        });
        setDeployedProviderIds(ids);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchProvidersList();
  }, [fetchProvidersList]);

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
    setTimeout(() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
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
        setTestResult({
          success: true,
          message: editingProviderId ? 'Provider updated!' : 'Provider saved!',
        });
        resetFormToNew();
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
      const usingBots = (bots || []).filter((b) => b.is_deployed && (b.stt_provider_id === providerId || b.tts_provider_id === providerId));
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

        <h2 className="type-display type-display-lg mb-3">
          Speech Engine
        </h2>
        <p className="type-body mb-6 max-w-[520px]">
          Connect a speech provider by entering your API key. Model and language
          selection is configured per-bot in the Bot section.
        </p>

        {/* Reusable Configured Providers List */}
        <ConfigCardList
          title="Active Speech Providers"
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
          renderSubtitle={(p) => (
            p.provider_type === 'deepgram'
              ? 'STT + TTS (Nova-3, Flux, Aura)'
              : p.provider_type === 'elevenlabs'
              ? 'TTS (Multilingual v2, Turbo v2.5)'
              : 'TTS (S1, S2 Pro, Voice Cloning)'
          )}
        />

        {/* Configuration pane */}
        <div className="glass-pane" ref={formRef}>
          <div className="flex justify-between items-center mb-4">
            <span className="type-micro">
              {editingProviderId ? `Edit "${form.name}" Provider` : 'Add Speech Provider'}
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
            {/* Provider Type Selection Cards */}
            <div>
              <label className="type-micro block mb-2">Select Provider *</label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {[
                  { type: 'deepgram', name: 'Deepgram', role: 'STT + TTS', desc: 'Real-time STT & Aura TTS' },
                  { type: 'elevenlabs', name: 'ElevenLabs', role: 'TTS', desc: 'Ultra-realistic voices' },
                  { type: 'fishaudio', name: 'Fish Audio', role: 'TTS', desc: 'Zero-shot voice cloning' },
                ].map((p) => {
                  const isSel = (selectedType || form.provider_type) === p.type;
                  return (
                    <div
                      key={p.type}
                      onClick={() => selectProvider(p.type)}
                      className={`p-3 rounded-xl border cursor-pointer transition-all ${
                        isSel
                          ? 'bg-emerald-500/10 border-emerald-400 shadow-[0_0_15px_rgba(52,211,153,0.15)]'
                          : 'bg-white/[0.03] border-white/10 hover:border-white/20 hover:bg-white/[0.05]'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-semibold text-white">{p.name}</span>
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-white/10 text-white/70">{p.role}</span>
                      </div>
                      <p className="text-[11px] text-white/40 leading-snug">{p.desc}</p>
                    </div>
                  );
                })}
              </div>
            </div>

            <div>
              <label className="type-micro block mb-1">Provider Name *</label>
              <input
                className="glass-input"
                placeholder="Provider name (e.g. Deepgram Speech)"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
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
                      testConnection(key, editingProviderId);
                    }, 600);
                  } else {
                    setTestResult(null);
                    setConnectionValid(false);
                  }
                }}
              />
            </div>

            {testing && (
              <div className="flex items-center gap-2 p-2.5 rounded-md bg-white/[0.03] border border-white/[0.06]">
                <span className="w-1.5 h-1.5 rounded-full bg-white/35 animate-pulse" />
                <span className="text-xs text-white/60">Verifying API key...</span>
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
                <span className="text-xs font-medium">{testResult.message}</span>
              </div>
            )}

            <button
              type="button"
              className={`action-btn mt-2 ${isFormValid ? 'action-btn--primary' : ''}`}
              onClick={handleSave}
              disabled={saving || !isFormValid}
            >
              {saving && <span className="loading-ring" />}
              {saving ? 'Saving...' : editingProviderId ? 'Update Provider' : 'Save Provider'}
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
          This speech provider is currently used by deployed bot(s). Undeploy them first before deleting.
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
        Are you sure you want to remove this speech provider? This action cannot be undone.
      </GlassModal>

      {/* Sidebar Hints */}
      <div className="journey-section__sidebar">
        <div className="section-hint">
          <div className="section-hint__title">Speech Capabilities</div>
          <div className="section-hint__body">
            Speech providers convert voice audio to text (STT) and synthesize assistant speech into audio (TTS).
          </div>
        </div>

        <div className="section-hint">
          <div className="section-hint__title">Voice Flexibility</div>
          <div className="section-hint__body">
            Deepgram handles lightning-fast conversational audio. ElevenLabs and Fish Audio offer lifelike natural speech.
          </div>
        </div>

        <div className="section-hint">
          <div className="section-hint__title">Per-Bot Configuration</div>
          <div className="section-hint__body">
            Once saved, assign different voices, models, and languages to individual bots in Step 3.
          </div>
        </div>
      </div>
    </div>
  );
}
