import { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';

const DEFAULT_SYSTEM_PROMPT = `You are a warm, highly engaging, and intelligent voice assistant companion. You speak naturally, concisely, and conversationally. Your primary mission is to guide the user through a structured 5-question check-in journey, validating their answers turn by turn before advancing to the next question.

### SPEECH & TONE RULES:
1. Concise Spoken Turns: Keep all responses to 1-2 short sentences (under 25 words total). Avoid long explanations.
2. Spoken Formatting: Never use markdown formatting (no asterisks, no bullet points, no bold, no headers, no emojis). Write numbers as words (e.g., "five" instead of "5").
3. Conversational Warmth: Be warm, empathetic, encouraging, and natural.
4. Natural Redirection: When the user gives an off-topic or unclear answer:
   - NEVER say generic phrases like "I didn't catch that", "Sorry, I didn't get that", or "Could you repeat that?".
   - ALWAYS acknowledge what the user actually said first to show you heard them (e.g., "Cats are awesome! But tell me...").
   - Then naturally, warmly redirect back to the active question.

### SEQUENTIAL 5-QUESTION FLOW:
You must ask these 5 questions in exact order, one at a time:

Question 1: "What should I call you?"
- Expected Answer: User's name or preferred nickname.

Question 2: "What do you do for work or focus on daily?"
- Expected Answer: Profession, role, student status, or main daily activity.

Question 3: "How are you feeling today, and how would you rate your week so far?"
- Expected Answer: Current mood, feeling, or rating of the week.

Question 4: "What is your main personal or career goal right now?"
- Expected Answer: A stated goal, ambition, or target outcome.

Question 5: "What is something you are grateful for today?"
- Expected Answer: Something specific or general the user appreciates.

### ANSWER VALIDATION & CONTROL LOGIC:
1. Valid Answer: If the user provides a direct, meaningful answer to the active question:
   - Provide a brief, warm 1-sentence acknowledgement (e.g., "Nice to meet you, Alex!", "That is a great goal to work towards.").
   - Immediately ask the NEXT question in sequence in the same turn.
2. Off-Topic / Unclear Answer: Acknowledge what they said warmly, then gently re-ask the active question without advancing.
3. User Correction: If the user corrects an earlier answer (e.g., "Actually, my name is Jordan, not Alex"):
   - Acknowledge the correction warmly (e.g., "Got it, Jordan! Thanks for clarifying.") and continue with the active question.
4. Completion: After Question 5 is validly answered, provide a warm 2-sentence closing summary reflecting their name and main goal, then end with a fond sign-off.`;

/**
 * BotIdentitySection — Bot name, description, voice selection, and system prompt.
 * - Clicking any configured bot opens its full configuration for editing.
 * - Pre-filled with comprehensive 7-question sequential validation system prompt.
 */
export function BotIdentitySection({ llmProviders = [], speechProviders = [], onBotCreated }) {
  const [bots, setBots] = useState([]);
  const [editingBotId, setEditingBotId] = useState(null);
  const [form, setForm] = useState({
    name: 'Voice Assistant',
    description: '7-Step Guided Conversation Assistant',
    system_prompt: DEFAULT_SYSTEM_PROMPT,
    llm_provider_id: '',
    llm_model: '',
    stt_provider_id: '',
    tts_provider_id: '',
  });

  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState(null);

  const [availableLlmModels, setAvailableLlmModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [customModelInput, setCustomModelInput] = useState(false);

  // Deletion modal state
  const [deletingBotId, setDeletingBotId] = useState(null);

  const fetchBotsList = useCallback(() => {
    fetch('/admin/api/bots')
      .then((r) => r.json())
      .then((data) => setBots(data || []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchBotsList();
  }, [fetchBotsList]);

  // Fetch models whenever an LLM Provider is selected
  const fetchModelsForProvider = useCallback(async (providerId) => {
    if (!providerId) {
      setAvailableLlmModels([]);
      return;
    }
    setLoadingModels(true);
    try {
      const res = await fetch('/admin/api/llm-providers/fetch-models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider_id: providerId }),
      });
      const data = await res.json();
      if (data?.models) {
        setAvailableLlmModels(data.models);
        if (data.models.length > 0) {
          setForm((prev) => ({ ...prev, llm_model: prev.llm_model || data.models[0].id }));
        }
      }
    } catch (err) {
      console.error('[BotIdentitySection] Error fetching models for provider:', err);
    }
    setLoadingModels(false);
  }, []);

  // Fetch models if provider is preselected or changed
  useEffect(() => {
    if (form.llm_provider_id) {
      fetchModelsForProvider(form.llm_provider_id);
    } else if (llmProviders.length > 0 && !editingBotId) {
      const defaultPid = llmProviders[0].id;
      setForm((prev) => ({ ...prev, llm_provider_id: defaultPid }));
      fetchModelsForProvider(defaultPid);
    }
  }, [llmProviders, fetchModelsForProvider, form.llm_provider_id, editingBotId]);

  // Pre-select speech providers if available
  useEffect(() => {
    if (!form.stt_provider_id && speechProviders.length > 0 && !editingBotId) {
      setForm((prev) => ({ ...prev, stt_provider_id: speechProviders[0].id }));
    }
    if (!form.tts_provider_id && speechProviders.length > 0 && !editingBotId) {
      setForm((prev) => ({ ...prev, tts_provider_id: speechProviders[0].id }));
    }
  }, [speechProviders, form.stt_provider_id, form.tts_provider_id, editingBotId]);

  const handleSelectBotForEdit = (bot) => {
    setEditingBotId(bot.id);
    setForm({
      name: bot.name || '',
      description: bot.description || '',
      system_prompt: bot.system_prompt || DEFAULT_SYSTEM_PROMPT,
      llm_provider_id: bot.llm_provider_id || '',
      llm_model: bot.llm_model || '',
      stt_provider_id: bot.stt_provider_id || '',
      tts_provider_id: bot.tts_provider_id || '',
    });
    setCustomModelInput(false);
    if (bot.llm_provider_id) {
      fetchModelsForProvider(bot.llm_provider_id);
    }
    setResult({ success: true, message: `Editing "${bot.name}". Modify configuration below and click Update.` });
  };

  const resetFormToNew = () => {
    setEditingBotId(null);
    setForm({
      name: 'Voice Assistant',
      description: '7-Step Guided Conversation Assistant',
      system_prompt: DEFAULT_SYSTEM_PROMPT,
      llm_provider_id: llmProviders[0]?.id || '',
      llm_model: '',
      stt_provider_id: speechProviders[0]?.id || '',
      tts_provider_id: speechProviders[0]?.id || '',
    });
    setCustomModelInput(false);
    setResult(null);
  };

  const handleLlmProviderChange = (e) => {
    const pid = e.target.value;
    setForm((prev) => ({ ...prev, llm_provider_id: pid, llm_model: '' }));
    setCustomModelInput(false);
    fetchModelsForProvider(pid);
  };

  const handleSave = async () => {
    if (!isFormValid) return;
    setSaving(true);
    setResult(null);
    try {
      const endpoint = editingBotId ? `/admin/api/bots/${editingBotId}` : '/admin/api/bots';
      const method = editingBotId ? 'PUT' : 'POST';

      const res = await fetch(endpoint, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (res.ok) {
        const savedId = data.id || editingBotId;
        await fetch(`/admin/api/bots/${savedId}/activate`, { method: 'POST' });
        setResult({
          success: true,
          message: editingBotId ? 'Bot updated & activated live for user session!' : 'Bot created & activated live for user session!',
          id: savedId,
        });
        onBotCreated?.(data);
        fetchBotsList();
      } else {
        setResult({ success: false, message: data.detail || 'Failed to save bot' });
      }
    } catch (err) {
      setResult({ success: false, message: err.message });
    }
    setSaving(false);
  };

  const confirmDeleteBot = async () => {
    if (!deletingBotId) return;
    await fetch(`/admin/api/bots/${deletingBotId}`, { method: 'DELETE' });
    setBots((prev) => prev.filter((b) => b.id !== deletingBotId));
    if (editingBotId === deletingBotId) {
      resetFormToNew();
    }
    setDeletingBotId(null);
  };

  // Mandatory validation for all required fields
  const isFormValid =
    form.name.trim() !== '' &&
    form.system_prompt.trim() !== '' &&
    form.llm_provider_id !== '' &&
    form.llm_model.trim() !== '' &&
    form.stt_provider_id !== '' &&
    form.tts_provider_id !== '';

  return (
    <div className="journey-section journey-section--split">
      <div className="journey-section__content">
        <div className="step-indicator">
          <span className="step-indicator__dot" />
          Step 3 of 4
        </div>

        <h2 className="type-display type-display-lg" style={{ marginBottom: '0.75rem' }}>
          Bot Identity
        </h2>
        <p className="type-body" style={{ marginBottom: '1.5rem', maxWidth: '520px' }}>
          Define who your bot is and how it behaves.
          Click any configured bot to view or edit its settings.
        </p>

        {/* Existing bots list */}
        {bots.length > 0 && (
          <div className="glass-pane" style={{ marginBottom: '1.5rem', padding: '1rem 1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <span className="type-micro">Configured Bots (Click to Edit)</span>
              {editingBotId && (
                <button
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
                  + Create New Bot
                </button>
              )}
            </div>

            {bots.map((b) => {
              const isSelected = editingBotId === b.id;
              const llmP = llmProviders.find((p) => p.id === b.llm_provider_id);
              const sttP = speechProviders.find((p) => p.id === b.stt_provider_id);
              const ttsP = speechProviders.find((p) => p.id === b.tts_provider_id);

              return (
                <div
                  key={b.id}
                  onClick={() => handleSelectBotForEdit(b)}
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
                    boxShadow: isSelected ? '0 0 16px rgba(0,0,0,0.5), 0 0 10px hsla(200, 60%, 40%, 0.2)' : 'none',
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
                        {b.name} {isSelected && <span style={{ fontSize: '11px', opacity: 0.8 }}>(Editing)</span>}
                      </div>
                      <div className="type-micro" style={{ fontSize: '10px', marginTop: '2px' }}>
                        LLM: {llmP?.name || b.llm_provider_id || 'N/A'} ({b.llm_model || 'N/A'}) • STT: {sttP?.name || 'N/A'} • TTS: {ttsP?.name || 'N/A'}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSelectBotForEdit(b);
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
                        setDeletingBotId(b.id);
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

        {/* Identity & Provider Selection glass pane */}
        <div className="glass-pane" style={{ marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <span className="type-micro">
              {editingBotId ? 'Edit Bot Identity & Provider Setup' : 'Identity & Provider Setup'}
            </span>
            {editingBotId && (
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
                Bot Name *
              </label>
              <input
                className="glass-input"
                placeholder="Bot name (e.g. Sales Assistant)"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>

            <div>
              <label className="type-micro" style={{ display: 'block', marginBottom: '4px' }}>
                Description (Optional)
              </label>
              <input
                className="glass-input"
                placeholder="Description"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </div>

            {/* Provider & Model Selectors */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <label className="type-micro" style={{ display: 'block', marginBottom: '4px' }}>
                  LLM Provider *
                </label>
                <select
                  className="glass-input glass-select"
                  value={form.llm_provider_id}
                  onChange={handleLlmProviderChange}
                >
                  <option value="" style={{ background: '#111' }}>Select LLM Provider</option>
                  {llmProviders.map((p) => (
                    <option key={p.id} value={p.id} style={{ background: '#111' }}>
                      {p.name} ({p.provider_type})
                    </option>
                  ))}
                </select>
              </div>

              {/* Interactive Dropdown Selector for LLM Model */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <label className="type-micro">LLM Model *</label>
                  {customModelInput ? (
                    <button
                      type="button"
                      onClick={() => setCustomModelInput(false)}
                      style={{ background: 'none', border: 'none', color: 'var(--accent-bright)', fontSize: '10px', cursor: 'pointer' }}
                    >
                      ← Select list
                    </button>
                  ) : (
                    loadingModels && <span style={{ fontSize: '10px', color: 'var(--ink-60)' }}>Loading models...</span>
                  )}
                </div>

                {!customModelInput ? (
                  <select
                    className="glass-input glass-select"
                    value={form.llm_model}
                    onChange={(e) => {
                      if (e.target.value === '__custom__') {
                        setCustomModelInput(true);
                        setForm({ ...form, llm_model: '' });
                      } else {
                        setForm({ ...form, llm_model: e.target.value });
                      }
                    }}
                    disabled={!form.llm_provider_id || loadingModels}
                  >
                    <option value="" style={{ background: '#111' }}>Select LLM Model</option>
                    {availableLlmModels.map((m) => (
                      <option key={m.id} value={m.id} style={{ background: '#111' }}>
                        {m.name || m.id}
                      </option>
                    ))}
                    <option value="__custom__" style={{ background: '#111', color: 'var(--accent-bright)' }}>
                      + Write custom model name...
                    </option>
                  </select>
                ) : (
                  <input
                    className="glass-input"
                    placeholder="Enter custom model name (e.g. gpt-4o, claude-3-5-sonnet)"
                    value={form.llm_model}
                    onChange={(e) => setForm({ ...form, llm_model: e.target.value })}
                  />
                )}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <label className="type-micro" style={{ display: 'block', marginBottom: '4px' }}>
                  STT Provider (Speech-to-Text) *
                </label>
                <select
                  className="glass-input glass-select"
                  value={form.stt_provider_id}
                  onChange={(e) => setForm({ ...form, stt_provider_id: e.target.value })}
                >
                  <option value="" style={{ background: '#111' }}>Select STT Provider</option>
                  {speechProviders.map((p) => (
                    <option key={p.id} value={p.id} style={{ background: '#111' }}>
                      {p.name} ({p.provider_type})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="type-micro" style={{ display: 'block', marginBottom: '4px' }}>
                  TTS Provider (Text-to-Speech) *
                </label>
                <select
                  className="glass-input glass-select"
                  value={form.tts_provider_id}
                  onChange={(e) => setForm({ ...form, tts_provider_id: e.target.value })}
                >
                  <option value="" style={{ background: '#111' }}>Select TTS Provider</option>
                  {speechProviders.map((p) => (
                    <option key={p.id} value={p.id} style={{ background: '#111' }}>
                      {p.name} ({p.provider_type})
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Master System Prompt glass pane */}
        <div className="glass-pane">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
            <label className="type-micro">Master 7-Question Validation System Prompt *</label>
            <button
              type="button"
              onClick={() => setForm((prev) => ({ ...prev, system_prompt: DEFAULT_SYSTEM_PROMPT }))}
              style={{ background: 'none', border: 'none', color: 'var(--accent-bright)', fontSize: '10px', cursor: 'pointer' }}
            >
              Reset to Default Prompt
            </button>
          </div>
          <textarea
            className="glass-input"
            rows={12}
            style={{ fontFamily: 'monospace', fontSize: '12px', lineHeight: '1.5' }}
            value={form.system_prompt}
            onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
          />

          {result && (
            <p style={{ fontSize: '13px', margin: '0.75rem 0 0', color: result.success ? 'var(--accent-bright)' : 'var(--warn)' }}>
              {result.success ? '✓ ' : '✗ '}{result.message}
            </p>
          )}

          <button
            className={`action-btn ${isFormValid ? 'action-btn--primary' : ''}`}
            onClick={handleSave}
            disabled={saving || !isFormValid}
            style={{
              marginTop: '1rem',
              width: '100%',
              opacity: isFormValid ? 1 : 0.4,
              cursor: isFormValid ? 'pointer' : 'not-allowed',
            }}
          >
            {saving && <span className="loading-ring" />}
            {saving ? 'Saving...' : editingBotId ? 'Update Bot Configuration' : 'Save & Connect Bot'}
          </button>
        </div>
      </div>

      {/* Delete Confirmation Modal — rendered in document.body for exact viewport centering */}
      {deletingBotId && createPortal(
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
              Are you sure you want to remove this Bot configuration? This action cannot be undone.
            </p>
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
              <button
                onClick={() => setDeletingBotId(null)}
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
                onClick={confirmDeleteBot}
                style={{
                  padding: '8px 18px',
                  background: 'var(--warn)',
                  border: 'none',
                  color: '#fff',
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

      {/* Sidebar hints */}
      <div className="journey-section__sidebar">
        <div className="section-hint">
          <div className="section-hint__title">System Prompt</div>
          <div className="section-hint__body">
            Defines your bot's identity, personality, knowledge boundaries, and behavioral tone.
          </div>
        </div>

        <div className="section-hint">
          <div className="section-hint__title">Provider Binding</div>
          <div className="section-hint__body">
            Bind your choice of LLM and Speech provider to power this specific bot instance.
          </div>
        </div>

        <div className="section-hint">
          <div className="section-hint__title">Voice Persona</div>
          <div className="section-hint__body">
            Configure voice IDs and speech parameters tailored to your bot's character.
          </div>
        </div>
      </div>
    </div>
  );
}
