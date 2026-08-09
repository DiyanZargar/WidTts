import { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';

/**
 * LanguageMultiSelect — Compact dropdown for selecting multiple languages with a primary indicator.
 * Clicking the dropdown opens a checklist. ★ marks the primary language.
 */
function LanguageMultiSelect({ languages, selected, primary, onChange, onSetPrimary, label }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const panelRef = useRef(null);
  const [panelPos, setPanelPos] = useState({ top: 0, left: 0, width: 0 });

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target) && panelRef.current && !panelRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  // Keep panel position synced on scroll/resize
  useEffect(() => {
    if (!open) return;
    const updatePos = () => {
      if (ref.current) {
        const rect = ref.current.getBoundingClientRect();
        setPanelPos({ top: rect.bottom + 4, left: rect.left, width: rect.width });
      }
    };
    window.addEventListener('scroll', updatePos, true);
    window.addEventListener('resize', updatePos);
    return () => { window.removeEventListener('scroll', updatePos, true); window.removeEventListener('resize', updatePos); };
  }, [open]);

  const openPanel = () => {
    if (ref.current) {
      const rect = ref.current.getBoundingClientRect();
      setPanelPos({ top: rect.bottom + 4, left: rect.left, width: rect.width });
    }
    setOpen(true);
  };

  const langs = languages.length > 0 ? languages : [{ code: 'en', name: 'English' }];
  const displayText = selected.length === 0
    ? 'None'
    : selected.length === 1
      ? langs.find(l => l.code === selected[0])?.name || selected[0]
      : `${langs.find(l => l.code === primary)?.name || primary} +${selected.length - 1}`;

  const toggle = (code) => {
    const next = selected.includes(code)
      ? selected.filter(c => c !== code)
      : [...selected, code];
    if (next.length === 0) return;
    onChange(next);
  };

  return (
    <div ref={ref} className="lang-dropdown">
      <label className="type-micro" style={{ display: 'block', marginBottom: '4px', fontSize: '9px' }}>{label}</label>
      <div
        onClick={() => open ? setOpen(false) : openPanel()}
        className="glass-input lang-dropdown__trigger"
      >
        <span className={`lang-dropdown__trigger-text ${selected.length === 0 ? 'lang-dropdown__trigger-text--empty' : ''}`}>
          {displayText}
        </span>
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0, opacity: 0.4 }}>
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      {open && createPortal(
        <div
          ref={panelRef}
          className="lang-dropdown__panel"
          style={{ position: 'fixed', top: panelPos.top, left: panelPos.left, width: panelPos.width }}
        >
          {langs.map((lang) => {
            const isSelected = selected.includes(lang.code);
            const isPrimary = primary === lang.code;
            return (
              <div
                key={lang.code}
                className={`lang-dropdown__item ${isSelected ? 'lang-dropdown__item--selected' : ''}`}
              >
                <div
                  onClick={() => toggle(lang.code)}
                  className={`lang-dropdown__checkbox ${isSelected ? 'lang-dropdown__checkbox--checked' : ''}`}
                >
                  {isSelected && (
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#000" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  )}
                </div>
                <span
                  onClick={() => toggle(lang.code)}
                  className={`lang-dropdown__label ${isSelected ? 'lang-dropdown__label--selected' : ''}`}
                >
                  {lang.name}
                </span>
                {isSelected && (
                  <span
                    onClick={(e) => { e.stopPropagation(); onSetPrimary(lang.code); }}
                    title="Set as primary"
                    className={`lang-dropdown__star ${isPrimary ? 'lang-dropdown__star--primary' : ''}`}
                  >
                    {isPrimary ? '★' : '☆'}
                  </span>
                )}
              </div>
            );
          })}
        </div>,
        document.body
      )}
    </div>
  );
}

/**
 * GlassSelect — Custom single-select dropdown with radio-style indicators.
 * Same look as LanguageMultiSelect but with radio buttons instead of checkboxes.
 */
function GlassSelect({ options, value, onChange, label, placeholder, disabled }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const panelRef = useRef(null);
  const [panelPos, setPanelPos] = useState({ top: 0, left: 0, width: 0 });

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target) && panelRef.current && !panelRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  // Keep panel position synced on scroll/resize
  useEffect(() => {
    if (!open) return;
    const updatePos = () => {
      if (ref.current) {
        const rect = ref.current.getBoundingClientRect();
        setPanelPos({ top: rect.bottom + 4, left: rect.left, width: rect.width });
      }
    };
    window.addEventListener('scroll', updatePos, true);
    window.addEventListener('resize', updatePos);
    return () => { window.removeEventListener('scroll', updatePos, true); window.removeEventListener('resize', updatePos); };
  }, [open]);

  const openPanel = () => {
    if (disabled) return;
    if (ref.current) {
      const rect = ref.current.getBoundingClientRect();
      setPanelPos({ top: rect.bottom + 4, left: rect.left, width: rect.width });
    }
    setOpen(true);
  };

  const selectedOption = options.find(o => o.value === value);
  const displayText = selectedOption ? selectedOption.label : (placeholder || 'Select...');

  return (
    <div ref={ref} className="glass-dropdown">
      {label && <label className="type-micro" style={{ display: 'block', marginBottom: '4px', fontSize: '9px' }}>{label}</label>}
      <div
        onClick={() => open ? setOpen(false) : openPanel()}
        className={`glass-input glass-dropdown__trigger ${disabled ? 'glass-dropdown__trigger--disabled' : ''}`}
        style={disabled ? { opacity: 0.4, cursor: 'not-allowed' } : {}}
      >
        <span className={`glass-dropdown__trigger-text ${!selectedOption ? 'glass-dropdown__trigger-text--empty' : ''}`}>
          {displayText}
        </span>
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0, opacity: 0.4 }}>
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>

      {open && createPortal(
        <div
          ref={panelRef}
          className="glass-dropdown__panel"
          style={{ position: 'fixed', top: panelPos.top, left: panelPos.left, width: panelPos.width }}
        >
          {options.map((opt) => {
            const isSelected = value === opt.value;
            return (
              <div
                key={opt.value}
                className={`glass-dropdown__item ${isSelected ? 'glass-dropdown__item--selected' : ''}`}
                onClick={() => { onChange(opt.value); setOpen(false); }}
              >
                <div className={`glass-dropdown__radio ${isSelected ? 'glass-dropdown__radio--selected' : ''}`}>
                  {isSelected && <div className="glass-dropdown__radio-dot" />}
                </div>
                <span className={`glass-dropdown__label ${isSelected ? 'glass-dropdown__label--selected' : ''}`}>
                  {opt.label}
                </span>
              </div>
            );
          })}
        </div>,
        document.body
      )}
    </div>
  );
}

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

const EMPTY_FORM = {
  name: '',
  description: '',
  system_prompt: '',
  llm_provider_id: '',
  llm_model: '',
  stt_provider_id: '',
  tts_provider_id: '',
  stt_model: '',
  tts_model: '',
  stt_languages: ['en'],
  stt_primary_language: 'en',
  tts_languages: ['en'],
  tts_primary_language: 'en',
};

/**
 * BotIdentitySection — Bot name, description, voice selection, system prompt,
 * speech model selection, and language configuration.
 */
export function BotIdentitySection({ llmProviders = [], speechProviders = [], onBotCreated }) {
  const [bots, setBots] = useState([]);
  const [editingBotId, setEditingBotId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState(null);

  // Auto-dismiss result toast after 5 seconds
  useEffect(() => {
    if (!result) return;
    const timer = setTimeout(() => setResult(null), 5000);
    return () => clearTimeout(timer);
  }, [result]);
  const [customModelInput, setCustomModelInput] = useState(false);
  const [deletingBotId, setDeletingBotId] = useState(null);

  // LLM models
  const [availableLlmModels, setAvailableLlmModels] = useState([]);
  const [loadingModels, setLoadingModels] = useState(false);

  // Speech models (fetched per provider type)
  const [sttModels, setSttModels] = useState([]);
  const [ttsModels, setTtsModels] = useState([]);
  const [availableLanguages, setAvailableLanguages] = useState([]);

  // Audio preview (Ported from dev branch SpeechSection)
  const [previewingModel, setPreviewingModel] = useState(null);
  const currentAudioRef = useRef(null);
  const abortControllerRef = useRef(null);
  const previewDebounceRef = useRef(null);

  // Dynamic Voice Profile calculation from dev branch
  const getVoiceProfile = useCallback((modelOrVoiceId = '') => {
    const id = modelOrVoiceId.toLowerCase();
    if (id.includes('flux')) return { pitch: 1.0, rate: 1.15, gender: 'unisex', freq: 320 };
    if (
      id.includes('asteria') || id.includes('luna') || id.includes('stella') ||
      id.includes('athena') || id.includes('hera') || id.includes('rachel') ||
      id.includes('domi') || id.includes('bella') || id.includes('elli')
    ) {
      if (id.includes('luna') || id.includes('elli')) return { pitch: 1.45, rate: 0.95, gender: 'female', freq: 440 };
      if (id.includes('stella') || id.includes('bella')) return { pitch: 1.25, rate: 1.05, gender: 'female', freq: 400 };
      if (id.includes('athena')) return { pitch: 1.15, rate: 0.9, gender: 'female', freq: 380 };
      if (id.includes('domi')) return { pitch: 1.35, rate: 1.1, gender: 'female', freq: 420 };
      return { pitch: 1.3, rate: 1.0, gender: 'female', freq: 410 };
    }
    if (
      id.includes('orion') || id.includes('arcas') || id.includes('perseus') ||
      id.includes('zeus') || id.includes('arnold') || id.includes('adam') ||
      id.includes('sam') || id.includes('rufus')
    ) {
      if (id.includes('arnold') || id.includes('zeus')) return { pitch: 0.58, rate: 0.85, gender: 'male', freq: 160 };
      if (id.includes('arcas') || id.includes('adam')) return { pitch: 0.78, rate: 1.02, gender: 'male', freq: 220 };
      if (id.includes('sam')) return { pitch: 0.85, rate: 1.1, gender: 'male', freq: 240 };
      return { pitch: 0.7, rate: 0.95, gender: 'male', freq: 190 };
    }
    let hash = 0;
    for (let i = 0; i < id.length; i++) hash = (hash << 5) - hash + id.charCodeAt(i);
    const pitch = 0.65 + (Math.abs(hash) % 85) / 100;
    const rate = 0.85 + (Math.abs(hash >> 3) % 40) / 100;
    const freq = 180 + (Math.abs(hash >> 2) % 300);
    return { pitch, rate, gender: pitch > 1.0 ? 'female' : 'male', freq };
  }, []);

  // Distinct voice profile synthesizer fallback from dev branch
  const playSynthesizedVoiceProfile = useCallback((voiceName = '') => {
    const profile = getVoiceProfile(voiceName);
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        const ctx = new AudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = profile.pitch < 0.9 ? 'sawtooth' : 'sine';
        osc.frequency.setValueAtTime(profile.freq, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(profile.freq * 1.2, ctx.currentTime + 0.15);
        gain.gain.setValueAtTime(0.12, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.35);
      }
    } catch (e) {}

    if (!('speechSynthesis' in window)) return;
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance("Hey, how's it going!");
      utterance.rate = profile.rate;
      utterance.pitch = profile.pitch;

      const voices = window.speechSynthesis.getVoices();
      if (voices.length > 0) {
        const genderMatches = voices.filter((v) => {
          const name = v.name.toLowerCase();
          if (profile.gender === 'female') return name.includes('female') || name.includes('samantha') || name.includes('victoria') || name.includes('zira');
          if (profile.gender === 'male') return name.includes('male') || name.includes('alex') || name.includes('daniel') || name.includes('david') || name.includes('fred');
          return true;
        });
        if (genderMatches.length > 0) {
          let hash = 0;
          for (let i = 0; i < voiceName.length; i++) hash = (hash << 5) - hash + voiceName.charCodeAt(i);
          utterance.voice = genderMatches[Math.abs(hash) % genderMatches.length];
        }
      }
      setTimeout(() => { try { window.speechSynthesis.speak(utterance); } catch (e) {} }, 20);
    } catch (e) {}
  }, [getVoiceProfile]);

  // Cancel any active audio or HTTP request immediately (from dev branch)
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
    if ('speechSynthesis' in window) {
      try { window.speechSynthesis.cancel(); } catch (e) {}
    }
    setPreviewingModel(null);
  }, []);

  // Hybrid audio sample greeting player from dev branch with immediate cancellation
  const playAudioGreeting = useCallback(async (ttsModel = '', voiceId = '') => {
    if (!form.tts_provider_id || !ttsModel) return;
    terminateActiveAudio();
    setPreviewingModel(ttsModel);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const payload = {
        provider_id: form.tts_provider_id,
        tts_model: ttsModel,
        tts_voice_id: voiceId,
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

        const blob = new Blob([arrayBuffer], { type: 'audio/wav' });
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
        setPreviewingModel(null);
        playSynthesizedVoiceProfile(ttsModel);
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.warn('[BotIdentity] Live preview failed, using profile fallback:', err);
        setPreviewingModel(null);
        playSynthesizedVoiceProfile(ttsModel);
      }
    }
  }, [form.tts_provider_id, terminateActiveAudio, playSynthesizedVoiceProfile]);

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
        setAvailableLanguages(data.languages || []);
      });
    } else {
      setSttModels([]);
    }
  }, [form.stt_provider_id, speechProviders, fetchSpeechModels]);

  // When TTS provider changes, fetch its models
  useEffect(() => {
    const provider = speechProviders.find(p => p.id === form.tts_provider_id);
    if (provider) {
      fetchSpeechModels(provider.provider_type).then(data => {
        const models = data.tts || [];
        setTtsModels(models);
        // Fire-and-forget: batch prewarm all TTS models in the backend cache
        // so selecting any model later is instant
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

  const handleLanguageToggle = (code) => {
    setForm(prev => {
      const langs = prev.languages.includes(code)
        ? prev.languages.filter(l => l !== code)
        : [...prev.languages, code];
      // Ensure at least one language
      if (langs.length === 0) return prev;
      // If primary was removed, set first remaining as primary
      const primary = langs.includes(prev.primary_language) ? prev.primary_language : langs[0];
      return { ...prev, languages: langs, primary_language: primary };
    });
  };

  const handleSetPrimaryLanguage = (code) => {
    setForm(prev => ({ ...prev, primary_language: code }));
  };

  const handleSave = async () => {
    if (!isFormValid) return;
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
              <span className="type-micro">Configured Bots (Click to Edit)</span>
              {editingBotId && (
                <button onClick={resetFormToNew} style={{ background: 'none', border: 'none', color: 'var(--accent-bright)', fontSize: '11px', cursor: 'pointer', fontWeight: 500 }}>
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
          </div>
        )}

        {/* Identity & Provider Selection */}
        <div className="glass-pane" style={{ marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <span className="type-micro">{editingBotId ? 'Edit Bot Identity & Provider Setup' : 'Identity & Provider Setup'}</span>
            {editingBotId && <button type="button" onClick={resetFormToNew} style={{ background: 'none', border: 'none', color: 'var(--ink-60)', fontSize: '11px', cursor: 'pointer' }}>Cancel Editing</button>}
          </div>

          <div style={{ display: 'grid', gap: '1rem' }}>
            <div>
              <label className="type-micro" style={{ display: 'block', marginBottom: '4px' }}>Bot Name *</label>
              <input className="glass-input" placeholder="Bot name (e.g. Sales Assistant)" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
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
                <GlassSelect
                  label="Model"
                  options={[{ value: '', label: 'Default' }, ...sttModels.map(m => ({ value: m.id, label: m.name }))]}
                  value={form.stt_model}
                  onChange={(val) => setForm({ ...form, stt_model: val })}
                  placeholder="Default"
                  disabled={!form.stt_provider_id}
                />
                <LanguageMultiSelect
                  languages={availableLanguages}
                  selected={form.stt_languages}
                  primary={form.stt_primary_language}
                  onChange={(selected) => setForm({ ...form, stt_languages: selected, stt_primary_language: selected.includes(form.stt_primary_language) ? form.stt_primary_language : (selected[0] || 'en') })}
                  onSetPrimary={(code) => setForm({ ...form, stt_primary_language: code })}
                  label="Languages"
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
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem' }}>
                <GlassSelect
                  label="Provider *"
                  options={speechProviders.map(p => ({ value: p.id, label: p.name }))}
                  value={form.tts_provider_id}
                  onChange={(val) => handleTtsProviderChange(val)}
                  placeholder="Select Provider"
                />
                <GlassSelect
                  label="Model"
                  options={[{ value: '', label: 'Default' }, ...ttsModels.map(m => ({ value: m.id, label: m.name }))]}
                  value={form.tts_model}
                  onChange={(val) => {
                    terminateActiveAudio();
                    setForm({ ...form, tts_model: val });
                    if (!val) return;
                    setPreviewingModel(val);
                    // Debounced API call (300ms) — only fires if user stops switching
                    // Prewarmed cache makes this near-instant
                    if (previewDebounceRef.current) clearTimeout(previewDebounceRef.current);
                    previewDebounceRef.current = setTimeout(() => {
                      playAudioGreeting(val);
                    }, 300);
                  }}
                  placeholder="Default"
                  disabled={!form.tts_provider_id}
                />
                <LanguageMultiSelect
                  languages={availableLanguages}
                  selected={form.tts_languages}
                  primary={form.tts_primary_language}
                  onChange={(selected) => setForm({ ...form, tts_languages: selected, tts_primary_language: selected.includes(form.tts_primary_language) ? form.tts_primary_language : (selected[0] || 'en') })}
                  onSetPrimary={(code) => setForm({ ...form, tts_primary_language: code })}
                  label="Languages"
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
