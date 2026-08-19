import { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { LanguageMultiSelect } from '../../common/LanguageMultiSelect';
import { GlassSelect } from '../../common/GlassSelect';
import { GlassComboBox } from '../../common/GlassComboBox';
import { ConfigCardList } from '../../common/ConfigCardList';
import { GlassModal } from '../../common/GlassModal';
import { DEFAULT_SYSTEM_PROMPT, EMPTY_FORM } from '../../../config/botTemplates';

/**
 * BotIdentitySection — Bot name, description, voice selection, system prompt,
 * speech model selection, and language configuration.
 */
export function BotIdentitySection({ llmProviders = [], speechProviders = [], onBotCreated, onNavigateToDeploy }) {
  const [bots, setBots] = useState([]);
  const [editingBotId, setEditingBotId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState(null);
  const [slugConfirm, setSlugConfirm] = useState(null); // { slug } when confirming new bot

  // Auto-dismiss result toast after 5 seconds
  useEffect(() => {
    if (!result) return;
    const timer = setTimeout(() => setResult(null), 5000);
    return () => clearTimeout(timer);
  }, [result]);
  const [customModelInput, setCustomModelInput] = useState(false);
  const [deletingBotId, setDeletingBotId] = useState(null);
  const formRef = useRef(null);

  // LLM models
  const [availableLlmModels, setAvailableLlmModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);

  // Speech models (fetched per provider type)
  const [sttModels, setSttModels] = useState([]);
  const [ttsModels, setTtsModels] = useState([]);
  const [ttsByLanguage, setTtsByLanguage] = useState({});
  const [sttByLanguage, setSttByLanguage] = useState({});
  const [availableLanguages, setAvailableLanguages] = useState([]);

  // Audio preview
  const [previewingModel, setPreviewingModel] = useState(null);
  const [previewError, setPreviewError] = useState(null);
  const currentAudioRef = useRef(null);
  const abortControllerRef = useRef(null);
  const previewDebounceRef = useRef(null);

  // Cancel any active audio or HTTP request immediately
  const terminateActiveAudio = useCallback(() => {
    if (previewDebounceRef.current) {
      clearTimeout(previewDebounceRef.current);
      previewDebounceRef.current = null;
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (currentAudioRef.current) {
      if (typeof currentAudioRef.current.stop === 'function') {
        currentAudioRef.current.stop();
      } else if (typeof currentAudioRef.current.pause === 'function') {
        currentAudioRef.current.pause();
        currentAudioRef.current.src = '';
      }
      currentAudioRef.current = null;
    }
    setPreviewingModel(null);
    setPreviewError(null);
  }, []);

  // Hybrid audio sample greeting player with immediate cancellation
  const playAudioGreeting = useCallback(async (ttsModel = '', voiceId = '') => {
    if (!form.tts_provider_id || !ttsModel) return;
    terminateActiveAudio();
    setPreviewingModel(ttsModel);
    setPreviewError(null);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Look up the provider's configured voice if none explicitly passed
    const provider = speechProviders.find((p) => p.id === form.tts_provider_id);
    const providerVoiceId = provider?.tts_voice_id || '';

    let resolvedModel = ttsModel;
    let resolvedVoiceId = voiceId || providerVoiceId;
    if (/^[0-9a-f]{24}$/i.test(ttsModel)) {
      // Fish Audio voice profile
      resolvedVoiceId = ttsModel;
      resolvedModel = '';
    } else if (/^[a-zA-Z0-9]{20}$/.test(ttsModel) && !ttsModel.startsWith('eleven_') && !ttsModel.startsWith('scribe_')) {
      // ElevenLabs voice profile
      resolvedVoiceId = ttsModel;
      resolvedModel = '';
    }

    try {
      const payload = {
        provider_id: form.tts_provider_id,
        tts_model: resolvedModel,
        tts_voice_id: resolvedVoiceId,
        text: "Hey, how's it going!",
      };

      const res = await fetch('/admin/api/speech-providers/sample-audio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      if (res.ok) {
        const arrayBuffer = await res.arrayBuffer();
        const contentType = res.headers.get('content-type') || 'audio/wav';
        const isMp3 = contentType.includes('mpeg') || contentType.includes('mp3');

        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) {
          try {
            const ctx = new AudioCtx();
            if (ctx.state === 'suspended') {
              await ctx.resume();
            }
            const audioBuffer = await ctx.decodeAudioData(arrayBuffer);
            const source = ctx.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(ctx.destination);
            currentAudioRef.current = { stop: () => { try { source.stop(); } catch(e){} } };

            source.onended = () => {
              setPreviewingModel(null);
              currentAudioRef.current = null;
            };

            source.start(0);
            return;
          } catch (decodeErr) {
            console.warn('[BotIdentity] Web Audio decode failed, falling back to HTMLAudio:', decodeErr);
          }
        }

        const blob = new Blob([arrayBuffer], { type: isMp3 ? 'audio/mpeg' : 'audio/wav' });
        const audioUrl = URL.createObjectURL(blob);
        const audio = new Audio(audioUrl);
        currentAudioRef.current = audio;

        audio.onended = () => {
          setPreviewingModel(null);
          URL.revokeObjectURL(audioUrl);
          currentAudioRef.current = null;
        };

        await audio.play();
      } else {
        let errorMsg = 'Voice preview failed';
        try {
          const errData = await res.json();
          errorMsg = errData.detail || `API error (${res.status})`;
          if (errorMsg.includes('payment_required') || errorMsg.includes('paid_plan_required')) {
            errorMsg = 'ElevenLabs: Free plan cannot use library voices — upgrade or use a custom voice';
          } else if (errorMsg.includes('Insufficient API credit')) {
            errorMsg = 'Fish Audio: Insufficient API credit — add funds at fish.audio/app/developers';
          }
        } catch { errorMsg = `API error (${res.status})`; }
        setPreviewingModel(null);
        setPreviewError(errorMsg);
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.warn('[BotIdentity] Live preview failed:', err);
        setPreviewingModel(null);
        setPreviewError(err.message || 'Voice preview failed — check network');
      }
    }
  }, [form.tts_provider_id, speechProviders, terminateActiveAudio]);

  const fetchBotsList = useCallback(() => {
    fetch('/admin/api/bots')
      .then((r) => r.json())
      .then((data) => setBots(data || []))
      .catch(() => {});
  }, []);

  useEffect(() => { fetchBotsList(); }, [fetchBotsList]);

  // Fetch LLM models when LLM provider changes
  const fetchModelsForProvider = useCallback(async (providerId) => {
    if (!providerId) { setAvailableLlmModels([]); return; }
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
        if (data.models.length > 0 && !form.llm_model) {
          setForm((prev) => ({ ...prev, llm_model: prev.llm_model || data.models[0].id }));
        }
      }
    } catch (err) { console.error('Error fetching LLM models:', err); }
    setLoadingModels(false);
  }, [form.llm_model]);

  // Fetch speech models when STT/TTS provider changes
  const fetchSpeechModels = useCallback(async (providerType) => {
    if (!providerType) return { stt: [], tts: [], languages: [] };
    try {
      const res = await fetch(`/admin/api/bots/speech-models/${providerType}`);
      return await res.json();
    } catch { return { stt: [], tts: [], languages: [] }; }
  }, []);

  // When STT provider changes, fetch its models
  useEffect(() => {
    const provider = speechProviders.find((p) => p.id === form.stt_provider_id);
    if (provider) {
      fetchSpeechModels(provider.provider_type).then((data) => {
        setSttModels(data.stt || []);
        setSttByLanguage(data.stt_by_language || {});
        setAvailableLanguages(data.languages || []);
      });
    } else {
      setSttModels([]);
      setSttByLanguage({});
    }
  }, [form.stt_provider_id, speechProviders, fetchSpeechModels]);

  // When TTS provider changes, fetch its models
  useEffect(() => {
    const provider = speechProviders.find((p) => p.id === form.tts_provider_id);
    if (provider) {
      fetchSpeechModels(provider.provider_type).then((data) => {
        const models = data.tts || [];
        setTtsModels(models);
        setTtsByLanguage(data.tts_by_language || {});
        if (data.languages?.length) setAvailableLanguages(data.languages);

        if (provider.provider_type === 'fishaudio' || provider.provider_type === 'elevenlabs') {
          fetch(`/admin/api/bots/speech-voices/${form.tts_provider_id}`)
            .then((r) => r.json())
            .then((voiceData) => {
              const voices = voiceData.voices || [];
              if (voices.length > 0) {
                setTtsByLanguage((prev) => {
                  const merged = { ...prev };
                  for (const v of voices) {
                    const lang = v.language || 'en';
                    if (!merged[lang]) merged[lang] = { language: { code: lang, name: lang }, voices: [] };
                    if (!merged[lang].voices.some((x) => x.id === v.id)) {
                      merged[lang].voices.push({ id: v.id, name: v.name });
                    }
                  }
                  return merged;
                });
              }
            })
            .catch(() => {});
        }
        if (models.length > 0) {
          fetch('/admin/api/speech-providers/prewarm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider_id: form.tts_provider_id, models: models.map((m) => m.id) }),
          }).catch(() => {});
        }
      });
    } else {
      setTtsModels([]);
      setTtsByLanguage({});
    }
  }, [form.tts_provider_id, speechProviders, fetchSpeechModels]);

  // Auto-select LLM provider on first load
  useEffect(() => {
    if (form.llm_provider_id) {
      fetchModelsForProvider(form.llm_provider_id);
    } else if (llmProviders.length > 0 && !editingBotId) {
      const defaultPid = llmProviders[0].id;
      setForm((prev) => ({ ...prev, llm_provider_id: defaultPid }));
      fetchModelsForProvider(defaultPid);
    }
  }, [llmProviders, fetchModelsForProvider, form.llm_provider_id, editingBotId]);

  // Auto-select speech providers on first load
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
      system_prompt: bot.system_prompt || '',
      llm_provider_id: bot.llm_provider_id || '',
      llm_model: bot.llm_model || '',
      stt_provider_id: bot.stt_provider_id || '',
      tts_provider_id: bot.tts_provider_id || '',
      stt_model: bot.stt_model || '',
      tts_model: bot.tts_model || '',
      tts_custom_model: bot.tts_custom_model || '',
      tts_custom_voice_id: bot.tts_custom_voice_id || '',
      tts_custom_endpoint: bot.tts_custom_endpoint || '',
      greeting: bot.greeting || '',
      stt_languages: bot.stt_languages || bot.languages || ['en'],
      stt_primary_language: bot.stt_primary_language || bot.primary_language || 'en',
      tts_languages: bot.tts_languages || bot.languages || ['en'],
      tts_primary_language: bot.tts_primary_language || bot.primary_language || 'en',
    });
    setCustomModelInput(false);
    if (bot.llm_provider_id) fetchModelsForProvider(bot.llm_provider_id);
    setResult({ success: true, message: `Editing "${bot.name}". Modify configuration below and click Update.` });
    setTimeout(() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
  };

  const resetFormToNew = () => {
    setEditingBotId(null);
    setForm({
      ...EMPTY_FORM,
      llm_provider_id: llmProviders[0]?.id || '',
      stt_provider_id: speechProviders[0]?.id || '',
      tts_provider_id: speechProviders[0]?.id || '',
    });
    setCustomModelInput(false);
    setResult(null);
  };

  const handleLlmProviderChange = (pid) => {
    setForm((prev) => ({ ...prev, llm_provider_id: pid, llm_model: '' }));
    setCustomModelInput(false);
    fetchModelsForProvider(pid);
  };

  const handleSttProviderChange = (pid) => {
    setForm((prev) => ({ ...prev, stt_provider_id: pid, stt_model: '' }));
  };

  const handleTtsProviderChange = (pid) => {
    setForm((prev) => ({ ...prev, tts_provider_id: pid, tts_model: '' }));
  };

  const handleSave = async () => {
    if (!isFormValid) return;
    if (!editingBotId) {
      const slug = form.name.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'bot';
      setSlugConfirm({ slug });
      return;
    }
    await doSave();
  };

  const doSave = async () => {
    setSlugConfirm(null);
    setSaving(true);
    setResult(null);
    try {
      const endpoint = editingBotId ? `/admin/api/bots/${editingBotId}` : '/admin/api/bots';
      const method = editingBotId ? 'PUT' : 'POST';
      const isEdit = Boolean(editingBotId);
      const botName = form.name;

      const res = await fetch(endpoint, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      let data;
      try {
        data = await res.json();
      } catch {
        const text = await res.text().catch(() => 'Unknown error');
        data = { detail: text || `Server error (${res.status})` };
      }
      if (res.ok) {
        const savedId = data.id || editingBotId;
        await fetch(`/admin/api/bots/${savedId}/activate`, { method: 'POST' });

        if (!isEdit) {
          setEditingBotId(null);
          setForm({
            ...EMPTY_FORM,
            llm_provider_id: llmProviders[0]?.id || '',
            stt_provider_id: speechProviders[0]?.id || '',
            tts_provider_id: speechProviders[0]?.id || '',
          });
          setCustomModelInput(false);
        }

        setResult({
          success: true,
          message: isEdit
            ? `"${botName}" configuration updated and set active!`
            : `"${botName}" created and activated!`,
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
    const bot = bots.find((b) => b.id === deletingBotId);
    if (bot?.is_deployed) {
      setResult({ success: false, message: `"${bot.name}" is deployed. Undeploy it first.` });
      setDeletingBotId(null);
      return;
    }
    await fetch(`/admin/api/bots/${deletingBotId}`, { method: 'DELETE' });
    setBots((prev) => prev.filter((b) => b.id !== deletingBotId));
    if (editingBotId === deletingBotId) resetFormToNew();
    setDeletingBotId(null);
  };

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

        <h2 className="type-display type-display-lg mb-3">
          Bot Persona & Intelligence
        </h2>
        <p className="type-body mb-6 max-w-[520px]">
          Define your bot's personality, assign speech models and voices from your configured
          providers, and set system instructions.
        </p>

        {/* Reusable Configured Bots List */}
        <ConfigCardList
          title="Configured Bots"
          count={bots.length}
          items={bots}
          selectedId={editingBotId}
          onSelect={handleSelectBotForEdit}
          onRemove={(id) => setDeletingBotId(id)}
          onAddNew={() => {
            resetFormToNew();
            setTimeout(() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
          }}
          addNewLabel="Add Bot"
          renderBadge={(b) => (
            b.is_deployed ? (
              <span
                onClick={(e) => {
                  e.stopPropagation();
                  onNavigateToDeploy?.(b.id);
                }}
                className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 font-semibold cursor-pointer hover:bg-emerald-500/25 transition"
              >
                DEPLOYED ↗
              </span>
            ) : null
          )}
          renderSubtitle={(b) => {
            const llm = llmProviders.find((p) => p.id === b.llm_provider_id);
            const stt = speechProviders.find((p) => p.id === b.stt_provider_id);
            const tts = speechProviders.find((p) => p.id === b.tts_provider_id);
            const parts = [
              b.llm_model || llm?.name,
              b.tts_model ? `Voice: ${b.tts_model}` : tts?.name,
              stt ? `STT: ${stt.name}` : null,
            ].filter(Boolean);
            return parts.join(' • ');
          }}
        />

        {/* Configuration pane */}
        <div className="glass-pane mb-6" ref={formRef}>
          <div className="flex justify-between items-center mb-4">
            <span className="type-micro">
              {editingBotId ? `Edit "${form.name}" Configuration` : 'New Bot Configuration'}
            </span>
            {editingBotId && (
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
            {/* Name + Description */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="type-micro block mb-1">Bot Name *</label>
                <input
                  className="glass-input"
                  placeholder="e.g. Maya AI"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </div>
              <div>
                <label className="type-micro block mb-1">Description</label>
                <input
                  className="glass-input"
                  placeholder="e.g. Senior Medical Assistant"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                />
              </div>
            </div>

            {/* Greeting */}
            <div>
              <label className="type-micro block mb-1">Opening Voice Greeting</label>
              <input
                className="glass-input"
                placeholder="e.g. Hello, I'm Maya! How can I help you today?"
                value={form.greeting}
                onChange={(e) => setForm({ ...form, greeting: e.target.value })}
              />
            </div>

            {/* LLM Provider + Model */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <GlassSelect
                label="LLM Provider *"
                options={llmProviders.map((p) => ({ value: p.id, label: `${p.name} (${p.provider_type})` }))}
                value={form.llm_provider_id}
                onChange={(val) => handleLlmProviderChange(val)}
                placeholder="Select LLM Provider"
              />
              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="type-micro">LLM Model *</label>
                  {customModelInput ? (
                    <button
                      type="button"
                      onClick={() => setCustomModelInput(false)}
                      className="text-[10px] text-emerald-400 hover:underline cursor-pointer"
                    >
                      ← Select list
                    </button>
                  ) : loadingModels && (
                    <span className="text-[10px] text-white/60">Loading...</span>
                  )}
                </div>
                {!customModelInput ? (
                  <GlassSelect
                    options={[
                      ...availableLlmModels.map((m) => ({ value: m.id, label: m.name || m.id })),
                      { value: '__custom__', label: '+ Write custom model...' },
                    ]}
                    value={form.llm_model}
                    onChange={(val) => {
                      if (val === '__custom__') {
                        setCustomModelInput(true);
                        setForm({ ...form, llm_model: '' });
                      } else {
                        setForm({ ...form, llm_model: val });
                      }
                    }}
                    placeholder="Select LLM Model"
                    disabled={!form.llm_provider_id || loadingModels}
                  />
                ) : (
                  <input
                    className="glass-input"
                    placeholder="Enter custom model name"
                    value={form.llm_model}
                    onChange={(e) => setForm({ ...form, llm_model: e.target.value })}
                  />
                )}
              </div>
            </div>

            {/* STT Configuration */}
            <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.06]">
              <label className="type-micro block mb-3 text-emerald-400">
                STT — Speech-to-Text
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <GlassSelect
                  label="Provider *"
                  options={speechProviders.map((p) => ({ value: p.id, label: p.name }))}
                  value={form.stt_provider_id}
                  onChange={(val) => handleSttProviderChange(val)}
                  placeholder="Select Provider"
                />
                <LanguageMultiSelect
                  languages={availableLanguages}
                  selected={form.stt_languages}
                  primary={form.stt_primary_language}
                  onChange={(selected) => {
                    const newPrimary = selected.includes(form.stt_primary_language)
                      ? form.stt_primary_language
                      : selected[0] || 'en';
                    setForm({ ...form, stt_languages: selected, stt_primary_language: newPrimary });
                  }}
                  onSetPrimary={(code) => {
                    setForm({ ...form, stt_primary_language: code });
                  }}
                  label="Language"
                />
                <GlassSelect
                  label="Model"
                  options={[
                    { value: '', label: 'Default' },
                    ...(sttByLanguage[form.stt_primary_language]?.models || []).map((m) => ({ value: m.id, label: m.name })),
                    ...sttModels
                      .filter((m) => !(sttByLanguage[form.stt_primary_language]?.models || []).some((x) => x.id === m.id))
                      .map((m) => ({ value: m.id, label: m.name })),
                  ]}
                  value={form.stt_model}
                  onChange={(val) => setForm({ ...form, stt_model: val })}
                  placeholder="Default"
                  disabled={!form.stt_provider_id}
                />
              </div>
            </div>

            {/* TTS Configuration */}
            <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.06]">
              <div className="flex items-center justify-between mb-3">
                <label className="type-micro text-emerald-400">
                  TTS — Text-to-Speech
                </label>
                {previewingModel && (
                  <span className="text-[10px] text-white/70 animate-pulse flex items-center gap-1">
                    🔊 Playing {previewingModel}...
                  </span>
                )}
              </div>

              {previewError && (
                <div className="mb-3 p-2.5 rounded-lg bg-red-500/10 border border-red-500/25 text-xs text-red-400 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-bold flex-shrink-0">⚠</span>
                    <span>{previewError}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setPreviewError(null)}
                    className="text-red-400 hover:text-white text-sm px-1.5"
                  >
                    ×
                  </button>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <GlassSelect
                  label="Provider *"
                  options={speechProviders.map((p) => ({ value: p.id, label: p.name }))}
                  value={form.tts_provider_id}
                  onChange={(val) => handleTtsProviderChange(val)}
                  placeholder="Select Provider"
                />
                <LanguageMultiSelect
                  languages={availableLanguages}
                  selected={form.tts_languages}
                  primary={form.tts_primary_language}
                  onChange={(selected) => {
                    const newPrimary = selected.includes(form.tts_primary_language)
                      ? form.tts_primary_language
                      : selected[0] || 'en';
                    setForm({ ...form, tts_languages: selected, tts_primary_language: newPrimary });
                  }}
                  onSetPrimary={(code) => {
                    setForm({ ...form, tts_primary_language: code });
                  }}
                  label="Language"
                />
                <GlassComboBox
                  label="Voice"
                  options={[
                    { value: '', label: 'Default' },
                    ...ttsModels.map((m) => ({ value: m.id, label: m.name })),
                    ...(ttsByLanguage[form.tts_primary_language]?.voices || [])
                      .filter((v) => !ttsModels.some((m) => m.id === v.id))
                      .map((v) => ({ value: v.id, label: v.name })),
                    ...Object.entries(ttsByLanguage)
                      .filter(([lang]) => lang !== form.tts_primary_language)
                      .flatMap(([, group]) => group.voices || [])
                      .filter((v) => !ttsModels.some((m) => m.id === v.id) && !(ttsByLanguage[form.tts_primary_language]?.voices || []).some((x) => x.id === v.id))
                      .map((v) => ({ value: v.id, label: v.name })),
                  ]}
                  value={form.tts_model}
                  onChange={(val) => {
                    terminateActiveAudio();
                    setForm({ ...form, tts_model: val });
                    if (!val) return;
                    setPreviewingModel(val);
                    if (previewDebounceRef.current) clearTimeout(previewDebounceRef.current);
                    previewDebounceRef.current = setTimeout(() => {
                      playAudioGreeting(val);
                    }, 300);
                  }}
                  placeholder="Select or type custom..."
                  disabled={!form.tts_provider_id}
                />
              </div>
            </div>
          </div>
        </div>

        {/* System Prompt */}
        <div className="glass-pane">
          <div className="flex justify-between items-center mb-1">
            <label className="type-micro">SYSTEM PROMPT *</label>
            <button
              type="button"
              onClick={() => setForm((prev) => ({ ...prev, system_prompt: DEFAULT_SYSTEM_PROMPT }))}
              className="text-[10px] text-emerald-400 hover:underline cursor-pointer"
            >
              Load Example Prompt
            </button>
          </div>
          <textarea
            className="glass-input font-mono text-xs leading-relaxed"
            rows={12}
            placeholder={DEFAULT_SYSTEM_PROMPT}
            value={form.system_prompt}
            onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
          />

          {/* Result Toast Portal */}
          {result && createPortal(
            <div className="fixed bottom-6 right-6 z-[99998] py-3 px-5 rounded-xl bg-black/80 border border-emerald-500/40 backdrop-blur-xl flex items-center gap-3 shadow-2xl animate-[halo-fade-in_200ms_ease-out] max-w-sm">
              <div
                className={`w-5 h-5 rounded-full flex items-center justify-center font-bold text-xs flex-shrink-0 ${
                  result.success ? 'bg-emerald-500 text-black' : 'bg-red-500 text-white'
                }`}
              >
                {result.success ? '✓' : '✕'}
              </div>
              <div>
                <div
                  className={`text-[10px] font-bold tracking-wider uppercase ${
                    result.success ? 'text-emerald-400' : 'text-red-400'
                  }`}
                >
                  {result.success ? 'Saved & Active' : 'Error'}
                </div>
                <div className="text-xs text-white/90 font-medium leading-snug">{result.message}</div>
              </div>
            </div>,
            document.body
          )}

          <button
            type="button"
            className={`action-btn mt-4 w-full ${isFormValid ? 'action-btn--primary' : ''}`}
            onClick={handleSave}
            disabled={saving || !isFormValid}
          >
            {saving && <span className="loading-ring" />}
            {saving ? 'Saving...' : editingBotId ? 'Update Bot Configuration' : 'Save & Connect Bot'}
          </button>
        </div>
      </div>

      {/* Reusable Delete Confirmation Modal */}
      {(() => {
        const targetBot = bots.find((b) => b.id === deletingBotId);
        const isDeployed = targetBot?.is_deployed;
        return (
          <GlassModal
            open={Boolean(deletingBotId)}
            title={isDeployed ? 'Cannot Delete' : 'Confirm Deletion'}
            onClose={() => setDeletingBotId(null)}
            footer={
              <div className="flex gap-3 justify-end">
                <button
                  type="button"
                  onClick={() => setDeletingBotId(null)}
                  className="action-btn text-xs py-1.5 px-4"
                >
                  {isDeployed ? 'Close' : 'Cancel'}
                </button>
                {!isDeployed && (
                  <button
                    type="button"
                    onClick={confirmDeleteBot}
                    className="action-btn action-btn--primary text-xs py-1.5 px-4 bg-amber-500 border-amber-500 text-black hover:bg-amber-400"
                  >
                    Delete
                  </button>
                )}
              </div>
            }
          >
            {isDeployed
              ? `"${targetBot?.name}" is currently deployed. Undeploy it first before deleting.`
              : 'Are you sure you want to remove this Bot configuration? This action cannot be undone.'}
          </GlassModal>
        );
      })()}

      {/* Reusable Slug Confirmation Modal */}
      <GlassModal
        open={Boolean(slugConfirm)}
        title="Confirm Bot Endpoint"
        onClose={() => setSlugConfirm(null)}
        footer={
          <div className="flex gap-3 justify-end">
            <button
              type="button"
              className="action-btn text-xs py-1.5 px-4"
              onClick={() => setSlugConfirm(null)}
            >
              Cancel
            </button>
            <button
              type="button"
              className="action-btn action-btn--primary text-xs py-1.5 px-4"
              onClick={() => doSave()}
            >
              Confirm & Save
            </button>
          </div>
        }
      >
        <p className="text-sm text-white/70 mb-2">Your bot will be accessible at:</p>
        <div className="p-2.5 mb-3 rounded-lg bg-emerald-500/10 border border-emerald-500/25 font-mono text-xs text-emerald-400">
          {window.location.origin}/bot/{slugConfirm?.slug}
        </div>
        <p className="text-xs text-white/40 leading-relaxed">
          The endpoint <strong className="text-white">/bot/{slugConfirm?.slug}</strong> will be permanent and cannot be changed after creation. The host URL adapts automatically wherever you deploy.
        </p>
      </GlassModal>

      {/* Sidebar hints */}
      <div className="journey-section__sidebar">
        <div className="section-hint">
          <div className="section-hint__title">System Prompt</div>
          <div className="section-hint__body">
            Defines your bot's identity, personality, knowledge boundaries, and behavioral tone.
          </div>
        </div>
        <div className="section-hint">
          <div className="section-hint__title">Speech Models</div>
          <div className="section-hint__body">
            Choose specific STT and TTS models from your configured providers. Each bot can use different models from the same provider.
          </div>
        </div>
        <div className="section-hint">
          <div className="section-hint__title">Languages</div>
          <div className="section-hint__body">
            Select supported languages for this bot. The primary language is used by default for speech recognition and synthesis.
          </div>
        </div>
      </div>
    </div>
  );
}
