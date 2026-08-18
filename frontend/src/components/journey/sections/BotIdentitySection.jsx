import { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { LanguageMultiSelect } from '../../common/LanguageMultiSelect';
import { GlassSelect } from '../../common/GlassSelect';
import { GlassComboBox } from '../../common/GlassComboBox';
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
  const [showAllBots, setShowAllBots] = useState(false);
  const formRef = useRef(null);
  const BOTS_VISIBLE = 3;

  // LLM models
  const [availableLlmModels, setAvailableLlmModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);

  // Speech models (fetched per provider type)
  const [sttModels, setSttModels] = useState([]);
  const [ttsModels, setTtsModels] = useState([]);
  const [ttsByLanguage, setTtsByLanguage] = useState({});
  const [sttByLanguage, setSttByLanguage] = useState({});
  const [availableLanguages, setAvailableLanguages] = useState([]);

  // Audio preview (Ported from dev branch SpeechSection)
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

  // Hybrid audio sample greeting player from dev branch with immediate cancellation
  const playAudioGreeting = useCallback(async (ttsModel = '', voiceId = '') => {
    if (!form.tts_provider_id || !ttsModel) return;
    terminateActiveAudio();
    setPreviewingModel(ttsModel);
    setPreviewError(null);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Look up the provider's configured voice if none explicitly passed
    const provider = speechProviders.find(p => p.id === form.tts_provider_id);
    const providerVoiceId = provider?.tts_voice_id || '';

    // Detect voice profile IDs vs engine model IDs:
    // - Fish Audio voice profiles: 24-char hex (MongoDB ObjectIds)
    // - ElevenLabs voice profiles: 20-char alphanumeric
    let resolvedModel = ttsModel;
    let resolvedVoiceId = voiceId || providerVoiceId;
    if (/^[0-9a-f]{24}$/i.test(ttsModel)) {
      // Fish Audio voice profile
      resolvedVoiceId = ttsModel;
      resolvedModel = '';
    } else if (/^[a-zA-Z0-9]{20}$/.test(ttsModel) && !ttsModel.startsWith('eleven_') && !ttsModel.startsWith('scribe_')) {
      // ElevenLabs voice profile (20-char alphanumeric, not a model ID)
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
        // Detect content type from response for correct playback
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
        // Extract the actual API error message
        let errorMsg = 'Voice preview failed';
        try {
          const errData = await res.json();
          errorMsg = errData.detail || `API error (${res.status})`;
          // Simplify common error patterns
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
      .catch(() => { });
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
    const provider = speechProviders.find(p => p.id === form.stt_provider_id);
    if (provider) {
      fetchSpeechModels(provider.provider_type).then(data => {
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
    const provider = speechProviders.find(p => p.id === form.tts_provider_id);
    if (provider) {
      fetchSpeechModels(provider.provider_type).then(data => {
        const models = data.tts || [];
        setTtsModels(models);
        setTtsByLanguage(data.tts_by_language || {});
        if (data.languages?.length) setAvailableLanguages(data.languages);

        // For Fish Audio & ElevenLabs: fetch real voice profiles from the provider API
        if (provider.provider_type === 'fishaudio' || provider.provider_type === 'elevenlabs') {
          fetch(`/admin/api/bots/speech-voices/${form.tts_provider_id}`)
            .then(r => r.json())
            .then(voiceData => {
              const voices = voiceData.voices || [];
              if (voices.length > 0) {
                // Merge real voices into tts_by_language (keep static entries too)
                setTtsByLanguage(prev => {
                  const merged = { ...prev };
                  for (const v of voices) {
                    const lang = v.language || 'en';
                    if (!merged[lang]) merged[lang] = { language: { code: lang, name: lang }, voices: [] };
                    // Avoid duplicate voice IDs
                    if (!merged[lang].voices.some(x => x.id === v.id)) {
                      merged[lang].voices.push({ id: v.id, name: v.name });
                    }
                  }
                  return merged;
                });
              }
            })
            .catch(() => {});
        }
          // Fire-and-forget: batch prewarm for all providers
          if (models.length > 0) {
            fetch('/admin/api/speech-providers/prewarm', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ provider_id: form.tts_provider_id, models: models.map(m => m.id) }),
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
    // On new bot creation, show slug confirmation first
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
          setForm({ ...EMPTY_FORM, llm_provider_id: llmProviders[0]?.id || '', stt_provider_id: speechProviders[0]?.id || '', tts_provider_id: speechProviders[0]?.id || '' });
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
    const bot = bots.find(b => b.id === deletingBotId);
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

  // Resolve provider types for model dropdowns
  const sttProviderType = speechProviders.find(p => p.id === form.stt_provider_id)?.provider_type || '';
  const ttsProviderType = speechProviders.find(p => p.id === form.tts_provider_id)?.provider_type || '';

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
              <span className="type-micro">Configured Bots ({bots.length})</span>
              <button
                onClick={() => { resetFormToNew(); setTimeout(() => formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100); }}
                style={{
                  background: 'var(--accent-bright)',
                  border: 'none',
                  color: '#000',
                  fontSize: '11px',
                  padding: '5px 14px',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  transition: 'opacity 200ms',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.85')}
                onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
              >
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                Add Bot
              </button>
            </div>
            {(showAllBots ? bots : bots.slice(0, BOTS_VISIBLE)).map((b) => {
              const isSelected = editingBotId === b.id;
              const llmP = llmProviders.find((p) => p.id === b.llm_provider_id);
              const sttP = speechProviders.find((p) => p.id === b.stt_provider_id);
              const ttsP = speechProviders.find((p) => p.id === b.tts_provider_id);
              return (
                <div
                  key={b.id}
                  onClick={() => handleSelectBotForEdit(b)}
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '12px 14px', marginBottom: '6px',
                    background: isSelected ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.02)',
                    border: `1px solid ${isSelected ? 'var(--accent-mid)' : 'rgba(255,255,255,0.06)'}`,
                    borderRadius: '8px', cursor: 'pointer', transition: 'all 200ms',
                    boxShadow: isSelected ? '0 0 16px rgba(0,0,0,0.5)' : 'none',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: isSelected ? 'var(--accent-bright)' : 'var(--ink-35)', boxShadow: isSelected ? '0 0 6px var(--accent-bright)' : 'none' }} />
                    <div>
                      <div style={{ color: isSelected ? 'var(--accent-bright)' : 'var(--ink-100)', fontSize: '14px', fontWeight: 500 }}>
                        {b.name} {isSelected && <span style={{ fontSize: '11px', opacity: 0.8 }}>(Editing)</span>}
                        {b.is_deployed && (
                          <span
                            style={{
                              display: 'inline-flex', alignItems: 'center', gap: '3px',
                              marginLeft: '8px', padding: '1px 6px', fontSize: '8px', fontWeight: 600,
                              letterSpacing: '0.06em', borderRadius: '3px',
                              background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.3)',
                              color: 'var(--accent-bright)',
                            }}
                          >
                            <span style={{ width: '4px', height: '4px', borderRadius: '50%', background: 'var(--accent-bright)' }} />
                            DEPLOYED
                          </span>
                        )}
                      </div>
                      <div className="type-micro" style={{ fontSize: '10px', marginTop: '2px' }}>
                        LLM: {llmP?.name || 'N/A'} • STT: {sttP?.name || 'N/A'}{b.stt_model ? ` (${b.stt_model})` : ''} • TTS: {ttsP?.name || 'N/A'}{b.tts_model ? ` (${b.tts_model})` : ''}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <button type="button" onClick={(e) => { e.stopPropagation(); handleSelectBotForEdit(b); }} style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.12)', color: 'var(--ink-90)', fontSize: '11px', padding: '4px 10px', borderRadius: '4px', cursor: 'pointer' }}>Edit</button>
                    <button type="button" onClick={(e) => { e.stopPropagation(); setDeletingBotId(b.id); }} style={{ background: 'none', border: 'none', color: 'var(--ink-35)', fontSize: '12px', cursor: 'pointer' }} onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--warn)')} onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--ink-35)')}>Remove</button>
                  </div>
                </div>
              );
            })}

            {bots.length > BOTS_VISIBLE && (
              <button
                onClick={() => setShowAllBots(!showAllBots)}
                style={{
                  width: '100%', padding: '8px', marginTop: '4px',
                  background: 'none', border: '1px dashed rgba(255,255,255,0.1)',
                  borderRadius: '6px', color: 'var(--ink-60)', fontSize: '11px',
                  cursor: 'pointer', transition: 'color 200ms',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--accent-bright)')}
                onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--ink-60)')}
              >
                {showAllBots ? 'Show less' : `Show ${bots.length - BOTS_VISIBLE} more`}
              </button>
            )}
          </div>
        )}

        {/* Identity & Provider Selection */}
        <div className="glass-pane" ref={formRef} style={{ marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <span className="type-micro">{editingBotId ? 'Edit Bot Identity & Provider Setup' : 'Identity & Provider Setup'}</span>
            {editingBotId && <button type="button" onClick={resetFormToNew} style={{ background: 'none', border: 'none', color: 'var(--ink-60)', fontSize: '11px', cursor: 'pointer' }}>Cancel Editing</button>}
          </div>

          <div style={{ display: 'grid', gap: '1rem' }}>
            <div>
              <label className="type-micro" style={{ display: 'block', marginBottom: '4px' }}>
                Bot Name * {editingBotId && <span style={{ color: 'var(--ink-35)', fontSize: '9px' }}>(locked — endpoint is permanent)</span>}
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  className="glass-input"
                  placeholder="Bot name (e.g. Sales Assistant)"
                  value={form.name}
                  disabled={Boolean(editingBotId)}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  style={editingBotId ? { opacity: 0.5, cursor: 'not-allowed', paddingRight: '36px' } : {}}
                />
                {editingBotId && (
                  <svg
                    width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--ink-35)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                    style={{ position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}
                  >
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                )}
              </div>
            </div>
            <div>
              <label className="type-micro" style={{ display: 'block', marginBottom: '4px' }}>Description (Optional)</label>
              <input className="glass-input" placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>

            {/* LLM Provider + Model */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <GlassSelect
                label="LLM Provider *"
                options={llmProviders.map(p => ({ value: p.id, label: `${p.name} (${p.provider_type})` }))}
                value={form.llm_provider_id}
                onChange={(val) => { handleLlmProviderChange(val); }}
                placeholder="Select LLM Provider"
              />
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <label className="type-micro">LLM Model *</label>
                  {customModelInput ? (
                    <button type="button" onClick={() => setCustomModelInput(false)} style={{ background: 'none', border: 'none', color: 'var(--accent-bright)', fontSize: '10px', cursor: 'pointer' }}>← Select list</button>
                  ) : loadingModels && <span style={{ fontSize: '10px', color: 'var(--ink-60)' }}>Loading...</span>}
                </div>
                {!customModelInput ? (
                  <GlassSelect
                    options={[...availableLlmModels.map(m => ({ value: m.id, label: m.name || m.id })), { value: '__custom__', label: '+ Write custom model...' }]}
                    value={form.llm_model}
                    onChange={(val) => { if (val === '__custom__') { setCustomModelInput(true); setForm({ ...form, llm_model: '' }); } else { setForm({ ...form, llm_model: val }); } }}
                    placeholder="Select LLM Model"
                    disabled={!form.llm_provider_id || loadingModels}
                  />
                ) : (
                  <input className="glass-input" placeholder="Enter custom model name" value={form.llm_model} onChange={(e) => setForm({ ...form, llm_model: e.target.value })} />
                )}
              </div>
            </div>

            {/* STT Configuration */}
            <div className="glass-pane" style={{ padding: '1rem 1.25rem', background: 'rgba(255,255,255,0.02)' }}>
              <label className="type-micro" style={{ display: 'block', marginBottom: '0.75rem', color: 'var(--accent-bright)' }}>
                STT — Speech-to-Text
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem' }}>
                <GlassSelect
                  label="Provider *"
                  options={speechProviders.map(p => ({ value: p.id, label: p.name }))}
                  value={form.stt_provider_id}
                  onChange={(val) => handleSttProviderChange(val)}
                  placeholder="Select Provider"
                />
                <LanguageMultiSelect
                  languages={availableLanguages}
                  selected={form.stt_languages}
                  primary={form.stt_primary_language}
                  onChange={(selected) => {
                    const newPrimary = selected.includes(form.stt_primary_language) ? form.stt_primary_language : (selected[0] || 'en');
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
                    // Language-matching models first
                    ...(sttByLanguage[form.stt_primary_language]?.models || []).map(m => ({ value: m.id, label: m.name })),
                    // Then all other models (deduplicated)
                    ...sttModels
                      .filter(m => !(sttByLanguage[form.stt_primary_language]?.models || []).some(x => x.id === m.id))
                      .map(m => ({ value: m.id, label: m.name })),
                  ]}
                  value={form.stt_model}
                  onChange={(val) => setForm({ ...form, stt_model: val })}
                  placeholder="Default"
                  disabled={!form.stt_provider_id}
                />
              </div>
            </div>

            {/* TTS Configuration */}
            <div className="glass-pane" style={{ padding: '1rem 1.25rem', background: 'rgba(255,255,255,0.02)' }}>
              <label className="type-micro" style={{ display: 'block', marginBottom: '0.75rem', color: 'var(--accent-bright)' }}>
                TTS — Text-to-Speech
                {previewingModel && (
                  <span style={{ marginLeft: '8px', fontSize: '10px', color: 'var(--ink-60)' }}>
                    🔊 Playing {previewingModel}...
                  </span>
                )}
              </label>
              {previewError && (
                <div style={{
                  marginBottom: '0.75rem', padding: '8px 12px', borderRadius: '6px',
                  background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)',
                  fontSize: '11px', color: '#f87171', lineHeight: '1.4',
                  display: 'flex', alignItems: 'center', gap: '8px',
                }}>
                  <span style={{ fontWeight: 700, flexShrink: 0 }}>⚠</span>
                  <span>{previewError}</span>
                  <button
                    onClick={() => setPreviewError(null)}
                    style={{ marginLeft: 'auto', background: 'none', border: 'none', color: '#f87171', cursor: 'pointer', fontSize: '14px', padding: '0 4px', opacity: 0.7 }}
                  >×</button>
                </div>
              )}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem' }}>
                <GlassSelect
                  label="Provider *"
                  options={speechProviders.map(p => ({ value: p.id, label: p.name }))}
                  value={form.tts_provider_id}
                  onChange={(val) => handleTtsProviderChange(val)}
                  placeholder="Select Provider"
                />
                <LanguageMultiSelect
                  languages={availableLanguages}
                  selected={form.tts_languages}
                  primary={form.tts_primary_language}
                  onChange={(selected) => {
                    const newPrimary = selected.includes(form.tts_primary_language) ? form.tts_primary_language : (selected[0] || 'en');
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
                    // TTS engine models (e.g. Fish Audio s2.1-pro, ElevenLabs eleven_v3)
                    ...ttsModels.map(m => ({ value: m.id, label: m.name })),
                    // Language-matching voices first
                    ...(ttsByLanguage[form.tts_primary_language]?.voices || [])
                      .filter(v => !ttsModels.some(m => m.id === v.id))
                      .map(m => ({ value: m.id, label: m.name })),
                    // Then all other voices (deduplicated)
                    ...Object.entries(ttsByLanguage)
                      .filter(([lang]) => lang !== form.tts_primary_language)
                      .flatMap(([, group]) => group.voices || [])
                      .filter(v => !ttsModels.some(m => m.id === v.id) && !(ttsByLanguage[form.tts_primary_language]?.voices || []).some(x => x.id === v.id))
                      .map(m => ({ value: m.id, label: m.name })),
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
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
            <label className="type-micro">SYSTEM PROMPT *</label>
            <button type="button" onClick={() => setForm((prev) => ({ ...prev, system_prompt: DEFAULT_SYSTEM_PROMPT }))} style={{ background: 'none', border: 'none', color: 'var(--accent-bright)', fontSize: '10px', cursor: 'pointer' }}>Load Example Prompt</button>
          </div>
          <textarea
            className="glass-input"
            rows={12}
            style={{ fontFamily: 'monospace', fontSize: '12px', lineHeight: '1.5' }}
            placeholder={DEFAULT_SYSTEM_PROMPT}
            value={form.system_prompt}
            onChange={(e) => setForm({ ...form, system_prompt: e.target.value })}
          />

          {/* Result toast — rendered via portal to avoid layout shift */}
          {result && createPortal(
            <div style={{
              position: 'fixed',
              bottom: '24px',
              right: '24px',
              zIndex: 99998,
              padding: '12px 20px',
              borderRadius: '10px',
              background: result.success ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
              border: `1px solid ${result.success ? 'rgba(16,185,129,0.4)' : 'rgba(239,68,68,0.4)'}`,
              backdropFilter: 'blur(20px)',
              WebkitBackdropFilter: 'blur(20px)',
              display: 'flex', alignItems: 'center', gap: '10px',
              boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
              animation: 'toast-in 300ms cubic-bezier(0.16, 1, 0.3, 1)',
              maxWidth: '360px',
            }}>
              <div style={{ width: '22px', height: '22px', borderRadius: '50%', background: result.success ? '#10b981' : '#ef4444', color: '#000', display: 'grid', placeItems: 'center', fontWeight: 800, fontSize: '12px', flexShrink: 0 }}>
                {result.success ? '✓' : '✕'}
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: '10px', color: result.success ? '#34d399' : '#f87171', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                  {result.success ? 'Saved & Active' : 'Error'}
                </div>
                <div style={{ fontSize: '12px', color: 'rgba(255,255,255,0.85)', fontWeight: 500 }}>{result.message}</div>
              </div>
            </div>,
            document.body
          )}

          <button
            className={`action-btn ${isFormValid ? 'action-btn--primary' : ''}`}
            onClick={handleSave}
            disabled={saving || !isFormValid}
            style={{ marginTop: '1rem', width: '100%', opacity: isFormValid ? 1 : 0.4, cursor: isFormValid ? 'pointer' : 'not-allowed' }}
          >
            {saving && <span className="loading-ring" />}
            {saving ? 'Saving...' : editingBotId ? 'Update Bot Configuration' : 'Save & Connect Bot'}
          </button>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {deletingBotId && (() => {
        const targetBot = bots.find(b => b.id === deletingBotId);
        const isDeployed = targetBot?.is_deployed;
        return createPortal(
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(12px)', display: 'grid', placeItems: 'center', zIndex: 99999 }}>
            <div className="glass-pane" style={{ width: '90%', maxWidth: '420px', padding: '2rem', textAlign: 'center' }}>
              <h3 style={{ fontFamily: 'var(--font-display)', color: 'var(--ink-100)', marginBottom: '0.75rem' }}>
                {isDeployed ? 'Cannot Delete' : 'Confirm Deletion'}
              </h3>
              <p style={{ fontSize: '13px', color: 'var(--ink-60)', marginBottom: '1.5rem' }}>
                {isDeployed
                  ? `"${targetBot?.name}" is currently deployed. Undeploy it first before deleting.`
                  : 'Are you sure you want to remove this Bot configuration? This action cannot be undone.'
                }
              </p>
              <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
                <button onClick={() => setDeletingBotId(null)} style={{ padding: '8px 18px', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.15)', color: 'var(--ink-100)', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}>
                  {isDeployed ? 'Close' : 'Cancel'}
                </button>
                {!isDeployed && (
                  <button onClick={confirmDeleteBot} style={{ padding: '8px 18px', background: 'var(--accent-mid)', border: 'none', color: '#000', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: 600 }}>Delete</button>
                )}
              </div>
            </div>
          </div>,
          document.body
        );
      })()}

      {/* Slug Confirmation Modal — first-time bot creation */}
      {slugConfirm && createPortal(
        <div
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(12px)', display: 'grid', placeItems: 'center', zIndex: 99999 }}
          onClick={(e) => { if (e.target === e.currentTarget) setSlugConfirm(null); }}
        >
          <div className="glass-pane" style={{ width: '90%', maxWidth: '440px', padding: '2rem', border: '1px solid rgba(16,185,129,0.2)' }}>
            <h3 style={{ fontFamily: 'var(--font-display)', color: 'var(--ink-100)', marginBottom: '0.75rem', fontSize: '18px' }}>
              Confirm bot endpoint
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--ink-60)', marginBottom: '1rem', lineHeight: '1.5' }}>
              Your bot will be accessible at:
            </p>
            <div style={{
              padding: '10px 14px', marginBottom: '1rem',
              background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)',
              borderRadius: '6px', fontFamily: 'monospace', fontSize: '13px',
              color: 'var(--accent-bright)',
            }}>
              {window.location.origin}/bot/{slugConfirm.slug}
            </div>
            <p style={{ fontSize: '12px', color: 'var(--ink-35)', marginBottom: '1.5rem', lineHeight: '1.5' }}>
              The endpoint <strong style={{ color: 'var(--ink-100)' }}>/bot/{slugConfirm.slug}</strong> will be permanent and cannot be changed after creation. The host URL adapts automatically wherever you deploy.
            </p>
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
              <button
                className="action-btn"
                onClick={() => setSlugConfirm(null)}
                style={{ fontSize: '12px', padding: '8px 16px' }}
              >
                Cancel
              </button>
              <button
                className="action-btn action-btn--primary"
                onClick={() => doSave()}
                style={{ fontSize: '12px', padding: '8px 20px' }}
              >
                Confirm & Save
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
          <div className="section-hint__body">Defines your bot's identity, personality, knowledge boundaries, and behavioral tone.</div>
        </div>
        <div className="section-hint">
          <div className="section-hint__title">Speech Models</div>
          <div className="section-hint__body">Choose specific STT and TTS models from your configured providers. Each bot can use different models from the same provider.</div>
        </div>
        <div className="section-hint">
          <div className="section-hint__title">Languages</div>
          <div className="section-hint__body">Select supported languages for this bot. The primary language is used by default for speech recognition and synthesis.</div>
        </div>
      </div>
    </div>
  );
}
