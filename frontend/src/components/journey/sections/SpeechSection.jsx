import { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';

/**
 * SpeechSection — Glass pane for speech provider configuration (Deepgram & ElevenLabs).
 * - Flux real-time TTS models included in Deepgram dropdown.
 * - Strict API key validation: invalid/garbage keys throw 401 Unauthorized errors instead of fake success.
 * - Immediate termination & cancellation of previous TTS greeting requests when selecting a new model.
 * - Saving or editing a provider keeps the provider selected so model changes greet immediately using saved credentials.
 * - Clean glass modal deletion confirmation.
 */
export function SpeechSection({ onProviderCreated }) {
  const [providers, setProviders] = useState([]);
  const [editingProviderId, setEditingProviderId] = useState(null);
  const [selectedType, setSelectedType] = useState(null); // 'deepgram' | 'elevenlabs'
  const [form, setForm] = useState({
    name: '',
    provider_type: 'deepgram',
    credentials: { api_key: '' },
    stt_model: '',
    stt_language: 'en',
    tts_model: '',
    tts_voice_id: '',
  });

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [sttModels, setSttModels] = useState([]);
  const [ttsModels, setTtsModels] = useState([]);
  const [ttsVoices, setTtsVoices] = useState([]);
  const [fetchingOptions, setFetchingOptions] = useState(false);
  const [connectionValid, setConnectionValid] = useState(false);

  // Custom model modes
  const [customSttMode, setCustomSttMode] = useState(false);
  const [customTtsMode, setCustomTtsMode] = useState(false);
  const [customVoiceMode, setCustomVoiceMode] = useState(false);

  // Audio greeting playback refs for instant cancellation of previous requests
  const [playingAudio, setPlayingAudio] = useState(false);
  const currentAudioRef = useRef(null);
  const abortControllerRef = useRef(null);

  // Deletion modal state
  const [deletingProviderId, setDeletingProviderId] = useState(null);

  const fetchProvidersList = useCallback(() => {
    fetch('/admin/api/speech-providers')
      .then((r) => r.json())
      .then((data) => setProviders(data || []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchProvidersList();
  }, [fetchProvidersList]);

  // Dynamic Voice Profile calculation
  const getVoiceProfile = useCallback((modelOrVoiceId = '', pType = 'deepgram') => {
    const id = modelOrVoiceId.toLowerCase();

    // Flux conversational models
    if (id.includes('flux')) {
      return { pitch: 1.0, rate: 1.15, gender: 'unisex', freq: 320 };
    }

    // Female voices: higher pitch, warm tone
    if (
      id.includes('asteria') || id.includes('luna') || id.includes('stella') ||
      id.includes('athena') || id.includes('hera') || id.includes('rachel') ||
      id.includes('domi') || id.includes('bella') || id.includes('elli') ||
      id.includes('21m00tcm4tlvdq8ikwam') || id.includes('aznzlk1xvdvuebnxmlld') || id.includes('exavitqu4vr4xnsdxmal') ||
      id.includes('mf3mgyeycl7xywbv9v6o')
    ) {
      if (id.includes('luna') || id.includes('elli')) return { pitch: 1.45, rate: 0.95, gender: 'female', freq: 440 };
      if (id.includes('stella') || id.includes('bella')) return { pitch: 1.25, rate: 1.05, gender: 'female', freq: 400 };
      if (id.includes('athena')) return { pitch: 1.15, rate: 0.9, gender: 'female', freq: 380 };
      if (id.includes('domi')) return { pitch: 1.35, rate: 1.1, gender: 'female', freq: 420 };
      return { pitch: 1.3, rate: 1.0, gender: 'female', freq: 410 };
    }

    // Male voices: deeper pitch, resonant bass
    if (
      id.includes('orion') || id.includes('arcas') || id.includes('perseus') ||
      id.includes('angler') || id.includes('zeus') || id.includes('antoni') ||
      id.includes('josh') || id.includes('arnold') || id.includes('adam') ||
      id.includes('sam') || id.includes('erxwobayin019pkysvjv') || id.includes('txgeqnhwrfwftfgw9xjx') ||
      id.includes('vr6aewltigwg4xsoukag') || id.includes('pninz6obpgdqgcfmajgb') || id.includes('yoz06amxzjj28mfd3poq')
    ) {
      if (id.includes('arnold') || id.includes('zeus')) return { pitch: 0.58, rate: 0.85, gender: 'male', freq: 160 };
      if (id.includes('arcas') || id.includes('adam')) return { pitch: 0.78, rate: 1.02, gender: 'male', freq: 220 };
      if (id.includes('josh') || id.includes('sam')) return { pitch: 0.85, rate: 1.1, gender: 'male', freq: 240 };
      if (id.includes('perseus') || id.includes('antoni')) return { pitch: 0.72, rate: 0.95, gender: 'male', freq: 200 };
      return { pitch: 0.7, rate: 0.95, gender: 'male', freq: 190 };
    }

    if (id.includes('aura-2')) {
      return { pitch: 1.12, rate: 1.08, gender: 'female', freq: 360 };
    }

    if (id.includes('flash') || id.includes('turbo')) {
      return { pitch: 1.05, rate: 1.22, gender: 'unisex', freq: 320 };
    }

    let hash = 0;
    for (let i = 0; i < id.length; i++) hash = (hash << 5) - hash + id.charCodeAt(i);
    const pitch = 0.65 + (Math.abs(hash) % 85) / 100;
    const rate = 0.85 + (Math.abs(hash >> 3) % 40) / 100;
    const freq = 180 + (Math.abs(hash >> 2) % 300);
    return { pitch, rate, gender: pitch > 1.0 ? 'female' : 'male', freq };
  }, []);

  // Distinct voice profile synthesizer fallback
  const playSynthesizedVoiceProfile = useCallback((voiceName = '') => {
    const profile = getVoiceProfile(voiceName, form.provider_type);

    setPlayingAudio(true);

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

    if (!('speechSynthesis' in window)) {
      setTimeout(() => setPlayingAudio(false), 1200);
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance("Hey, how's it going!");
    utterance.rate = profile.rate;
    utterance.pitch = profile.pitch;

    const voices = window.speechSynthesis.getVoices();
    if (voices.length > 0) {
      const genderMatches = voices.filter((v) => {
        const name = v.name.toLowerCase();
        if (profile.gender === 'female') {
          return name.includes('female') || name.includes('samantha') || name.includes('victoria') || name.includes('karen') || name.includes('zira') || name.includes('fiona') || name.includes('monika');
        } else if (profile.gender === 'male') {
          return name.includes('male') || name.includes('alex') || name.includes('daniel') || name.includes('david') || name.includes('fred') || name.includes('george') || name.includes('rishi');
        }
        return true;
      });

      if (genderMatches.length > 0) {
        let hash = 0;
        for (let i = 0; i < voiceName.length; i++) hash = (hash << 5) - hash + voiceName.charCodeAt(i);
        const selectedVoice = genderMatches[Math.abs(hash) % genderMatches.length];
        utterance.voice = selectedVoice;
      }
    }

    utterance.onstart = () => setPlayingAudio(true);
    utterance.onend = () => setPlayingAudio(false);
    utterance.onerror = () => setPlayingAudio(false);

    setTimeout(() => {
      window.speechSynthesis.speak(utterance);
    }, 50);
  }, [form.provider_type, getVoiceProfile]);

  // Cancel any active audio or HTTP request immediately
  const terminateActiveAudio = useCallback(() => {
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
      window.speechSynthesis.cancel();
    }
    setPlayingAudio(false);
  }, []);

  // Hybrid audio sample greeting player with immediate cancellation of previous requests
  const playAudioGreeting = useCallback(async (ttsModel = '', voiceId = '') => {
    // Terminate any previous playing audio or in-flight fetch request instantly!
    terminateActiveAudio();

    const key = form.credentials.api_key;
    const targetModel = ttsModel || form.tts_model;
    const targetVoice = voiceId || form.tts_voice_id;
    const voiceTag = targetVoice || targetModel || 'default';

    setPlayingAudio(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const payload = {
        provider_type: form.provider_type,
        tts_model: targetModel,
        tts_voice_id: targetVoice,
        text: "Hey, how's it going!",
      };

      if (key.trim() !== '') {
        payload.api_key = key.trim();
      } else if (editingProviderId) {
        payload.provider_id = editingProviderId;
      }

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
              setPlayingAudio(false);
              currentAudioRef.current = null;
            };

            source.start(0);
            setTestResult({ success: true, message: `Playing live API neural voice from ${form.provider_type}!` });
            return;
          } catch (decodeErr) {
            console.warn('[SpeechSection] Web Audio decode failed, falling back to HTMLAudio:', decodeErr);
          }
        }

        const blob = new Blob([arrayBuffer], { type: 'audio/wav' });
        const audioUrl = URL.createObjectURL(blob);
        const audio = new Audio(audioUrl);
        currentAudioRef.current = audio;

        audio.onended = () => {
          setPlayingAudio(false);
          URL.revokeObjectURL(audioUrl);
          currentAudioRef.current = null;
        };
        audio.onerror = () => {
          setPlayingAudio(false);
          URL.revokeObjectURL(audioUrl);
          currentAudioRef.current = null;
        };

        await audio.play();
        setTestResult({ success: true, message: `Playing live API neural voice from ${form.provider_type}!` });
        return;
      } else {
        const errData = await res.json().catch(() => ({}));
        setTestResult({
          success: false,
          message: errData.detail || `Speech API error (${res.status}). Enter a valid API key to test live voice.`,
        });
      }
    } catch (err) {
      if (err.name === 'AbortError') return; // Silent abort on model switch
      console.warn('[SpeechSection] Live API audio synthesis failed, using voice profile fallback:', err);
    }

    // Play distinct voice profile fallback if API request wasn't aborted
    playSynthesizedVoiceProfile(voiceTag);
  }, [form.provider_type, form.credentials.api_key, form.tts_model, form.tts_voice_id, editingProviderId, playSynthesizedVoiceProfile, terminateActiveAudio]);

  // Automatic background speech models & voices discovery with strict key verification
  const autoFetchSpeechOptions = useCallback(async (type, key, providerId = null) => {
    const pType = type !== undefined ? type : form.provider_type;
    const pKey = key !== undefined ? key : form.credentials.api_key;
    const pId = providerId !== null ? providerId : editingProviderId;

    if (!pKey && !pId) return;

    setFetchingOptions(true);
    try {
      const bodyPayload = pId && !pKey
        ? { provider_id: pId, provider_type: pType }
        : { provider_type: pType, api_key: pKey };

      const res = await fetch('/admin/api/speech-providers/fetch-models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(bodyPayload),
      });
      const data = await res.json();

      if (res.ok && data) {
        setSttModels(data.stt_models || []);
        setTtsModels(data.tts_models || []);
        setTtsVoices(data.tts_voices || []);
        setConnectionValid(true);
        setTestResult({
          success: true,
          message: `Connected to ${pType}! Discovered ${data.stt_models?.length || 0} STT & ${data.tts_models?.length || 0} TTS models.`,
        });
      } else {
        setConnectionValid(false);
        setTestResult({
          success: false,
          message: data.detail || `Invalid API key for ${pType}. Unauthorized by speech provider.`,
        });
      }
    } catch (err) {
      if (!pId) setConnectionValid(false);
      setTestResult({ success: false, message: `Speech API connection error: ${err.message}` });
    }
    setFetchingOptions(false);
  }, [form.provider_type, form.credentials.api_key, editingProviderId]);

  const handleSelectForEdit = (provider) => {
    setEditingProviderId(provider.id);
    setSelectedType(provider.provider_type);
    setForm({
      name: provider.name || '',
      provider_type: provider.provider_type || 'deepgram',
      credentials: { api_key: '' }, // empty means keep saved encrypted key
      stt_model: provider.stt_model || '',
      stt_language: provider.stt_language || 'en',
      tts_model: provider.tts_model || '',
      tts_voice_id: provider.tts_voice_id || '',
    });
    setConnectionValid(true);
    setTestResult({ success: true, message: `Editing "${provider.name}". Modify any field below and click Update.` });

    autoFetchSpeechOptions(provider.provider_type, '', provider.id);
  };

  const resetFormToNew = () => {
    terminateActiveAudio();
    setEditingProviderId(null);
    setSelectedType(null);
    setForm({
      name: '',
      provider_type: 'deepgram',
      credentials: { api_key: '' },
      stt_model: '',
      stt_language: 'en',
      tts_model: '',
      tts_voice_id: '',
    });
    setCustomSttMode(false);
    setCustomTtsMode(false);
    setCustomVoiceMode(false);
    setTestResult(null);
    setConnectionValid(false);
  };

  const selectProvider = (type) => {
    terminateActiveAudio();
    setSelectedType(type);
    setForm((prev) => ({
      ...prev,
      provider_type: type,
      name: prev.name || (type === 'deepgram' ? 'Deepgram Speech' : 'ElevenLabs Speech'),
    }));
    setCustomSttMode(false);
    setCustomTtsMode(false);
    setCustomVoiceMode(false);
    setTestResult(null);
    autoFetchSpeechOptions(type, form.credentials.api_key, editingProviderId);
  };

  const handleSave = async () => {
    if (!form.name || !form.stt_model || !form.tts_model) return;
    if (form.provider_type === 'elevenlabs' && !form.tts_voice_id) return;

    setTesting(true);
    setTestResult(null);
    try {
      const endpoint = editingProviderId
        ? `/admin/api/speech-providers/${editingProviderId}`
        : '/admin/api/speech-providers';
      const method = editingProviderId ? 'PUT' : 'POST';

      const payload = {
        name: form.name,
        provider_type: form.provider_type,
        stt_model: form.stt_model,
        stt_language: form.stt_language,
        tts_model: form.tts_model,
        tts_voice_id: form.tts_voice_id,
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
        setEditingProviderId(savedId); // KEEP SELECTED in edit mode!
        setConnectionValid(true);
        setForm((prev) => ({ ...prev, credentials: { api_key: '' } })); // Clear key input field to show saved state
        setTestResult({
          success: true,
          message: editingProviderId ? 'Speech Provider updated successfully!' : 'Speech Provider verified & saved successfully!',
        });
        onProviderCreated?.(data);
        fetchProvidersList();
      } else {
        setTestResult({ success: false, message: data.detail || 'Failed to save speech provider' });
      }
    } catch (err) {
      setTestResult({ success: false, message: err.message });
    }
    setTesting(false);
  };

  const confirmDelete = async () => {
    if (!deletingProviderId) return;
    terminateActiveAudio();
    await fetch(`/admin/api/speech-providers/${deletingProviderId}`, { method: 'DELETE' });
    setProviders((prev) => prev.filter((p) => p.id !== deletingProviderId));
    if (editingProviderId === deletingProviderId) {
      resetFormToNew();
    }
    setDeletingProviderId(null);
  };

  const isFormValid = editingProviderId
    ? form.name.trim() !== '' &&
      form.stt_model.trim() !== '' &&
      form.tts_model.trim() !== '' &&
      (form.provider_type !== 'elevenlabs' || form.tts_voice_id.trim() !== '')
    : form.name.trim() !== '' &&
      form.credentials.api_key.trim() !== '' &&
      form.stt_model.trim() !== '' &&
      form.tts_model.trim() !== '' &&
      (form.provider_type !== 'elevenlabs' || form.tts_voice_id.trim() !== '') &&
      connectionValid;

  return (
    <div className="journey-section journey-section--split">
      <div className="journey-section__content">
        <div className="step-indicator">
          <span className="step-indicator__dot" />
          Step 3 of 5
        </div>

        <h2 className="type-display type-display-lg" style={{ marginBottom: '0.75rem' }}>
          Speech Engine
        </h2>
        <p className="type-body" style={{ marginBottom: '1.5rem', maxWidth: '520px' }}>
          Select a speech provider for real-time voice recognition (STT) and speech synthesis (TTS).
          Click any active provider to view or edit its settings.
        </p>

        {/* Existing providers list */}
        {providers.length > 0 && (
          <div className="glass-pane" style={{ marginBottom: '1.5rem', padding: '1rem 1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <span className="type-micro">Active Speech Providers (Click to Edit)</span>
              {editingProviderId && (
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
                      </div>
                      <div className="type-micro" style={{ fontSize: '10px', marginTop: '2px' }}>
                        {p.provider_type} • STT: {p.stt_model || 'N/A'} • TTS: {p.tts_model || 'N/A'}
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

        {/* Provider selection buttons */}
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
          {['deepgram', 'elevenlabs'].map((type) => (
            <button
              key={type}
              onClick={() => selectProvider(type)}
              style={{
                flex: 1,
                padding: '1.5rem',
                background: selectedType === type ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.02)',
                border: `1px solid ${selectedType === type ? 'var(--accent-mid)' : 'rgba(255,255,255,0.08)'}`,
                borderRadius: '12px',
                cursor: 'pointer',
                transition: 'all 300ms cubic-bezier(0.16, 1, 0.3, 1)',
                textAlign: 'center',
                transform: selectedType === type ? 'scale(1.02)' : 'scale(1)',
                boxShadow: selectedType === type ? '0 0 20px 2px hsla(275, 60%, 40%, 0.15)' : 'none',
              }}
              aria-label={`Select ${type}`}
            >
              <span
                style={{
                  display: 'block',
                  fontFamily: 'var(--font-display)',
                  fontSize: '16px',
                  fontWeight: 400,
                  color: selectedType === type ? 'var(--accent-bright)' : 'var(--ink-60)',
                  marginBottom: '6px',
                  transition: 'color 300ms',
                }}
              >
                {type === 'deepgram' ? 'Deepgram' : 'ElevenLabs'}
              </span>
              <span className="type-micro" style={{ fontSize: '10px' }}>
                {type === 'deepgram' ? 'Flux / Nova-3 STT + Flux / Aura-2 TTS' : 'Scribe STT + Flash v2.5 TTS'}
              </span>
            </button>
          ))}
        </div>

        {/* Configuration Pane */}
        {selectedType && (
          <div className="glass-pane">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <span className="type-micro">
                {editingProviderId ? `Edit "${form.name}" Provider` : `Configure ${selectedType === 'deepgram' ? 'Deepgram' : 'ElevenLabs'}`}
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
                  placeholder="Provider Name"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
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
                    autoFetchSpeechOptions(form.provider_type, key, editingProviderId);
                  }}
                />
              </div>

              {fetchingOptions && (
                <p style={{ fontSize: '12px', color: 'var(--ink-60)', margin: 0 }}>
                  ⏳ Discovering models & voices...
                </p>
              )}

              {/* STT & TTS Model Selectors */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <label className="type-micro">STT Model *</label>
                    {customSttMode && (
                      <button
                        type="button"
                        onClick={() => setCustomSttMode(false)}
                        style={{ background: 'none', border: 'none', color: 'var(--accent-bright)', fontSize: '10px', cursor: 'pointer' }}
                      >
                        ← Select list
                      </button>
                    )}
                  </div>

                  {!customSttMode ? (
                    <select
                      className="glass-input glass-select"
                      value={form.stt_model}
                      onChange={(e) => {
                        if (e.target.value === '__custom__') {
                          setCustomSttMode(true);
                          setForm({ ...form, stt_model: '' });
                        } else {
                          setForm({ ...form, stt_model: e.target.value });
                        }
                      }}
                    >
                      <option value="" style={{ background: '#111' }}>Select STT Model</option>
                      {sttModels.map((m) => (
                        <option key={m.id} value={m.id} style={{ background: '#111' }}>
                          {m.name}
                        </option>
                      ))}
                      <option value="__custom__" style={{ background: '#111', color: 'var(--accent-bright)' }}>
                        + Write custom model name...
                      </option>
                    </select>
                  ) : (
                    <input
                      className="glass-input"
                      placeholder="e.g. flux, nova-3"
                      value={form.stt_model}
                      onChange={(e) => setForm({ ...form, stt_model: e.target.value })}
                    />
                  )}
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <label className="type-micro">TTS Model *</label>
                    {customTtsMode && (
                      <button
                        type="button"
                        onClick={() => setCustomTtsMode(false)}
                        style={{ background: 'none', border: 'none', color: 'var(--accent-bright)', fontSize: '10px', cursor: 'pointer' }}
                      >
                        ← Select list
                      </button>
                    )}
                  </div>

                  {!customTtsMode ? (
                    <select
                      className="glass-input glass-select"
                      value={form.tts_model}
                      onChange={(e) => {
                        if (e.target.value === '__custom__') {
                          setCustomTtsMode(true);
                          setForm({ ...form, tts_model: '' });
                        } else {
                          const tModel = e.target.value;
                          setForm({ ...form, tts_model: tModel });
                          if (tModel) playAudioGreeting(tModel, form.tts_voice_id);
                        }
                      }}
                    >
                      <option value="" style={{ background: '#111' }}>Select TTS Model</option>
                      {ttsModels.map((m) => (
                        <option key={m.id} value={m.id} style={{ background: '#111' }}>
                          {m.name}
                        </option>
                      ))}
                      <option value="__custom__" style={{ background: '#111', color: 'var(--accent-bright)' }}>
                        + Write custom model name...
                      </option>
                    </select>
                  ) : (
                    <input
                      className="glass-input"
                      placeholder="e.g. flux-rufus-en, eleven_flash_v2_5, aura-2"
                      value={form.tts_model}
                      onChange={(e) => {
                        const val = e.target.value;
                        setForm((prev) => ({ ...prev, tts_model: val }));
                        if (val.trim().length >= 4) {
                          playAudioGreeting(val, form.tts_voice_id);
                        }
                      }}
                    />
                  )}
                </div>
              </div>

              {selectedType === 'elevenlabs' && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <label className="type-micro">TTS Voice ID *</label>
                    {customVoiceMode && (
                      <button
                        type="button"
                        onClick={() => setCustomVoiceMode(false)}
                        style={{ background: 'none', border: 'none', color: 'var(--accent-bright)', fontSize: '10px', cursor: 'pointer' }}
                      >
                        ← Select list
                      </button>
                    )}
                  </div>

                  {!customVoiceMode ? (
                    <select
                      className="glass-input glass-select"
                      value={form.tts_voice_id}
                      onChange={(e) => {
                        if (e.target.value === '__custom__') {
                          setCustomVoiceMode(true);
                          setForm({ ...form, tts_voice_id: '' });
                        } else {
                          const vId = e.target.value;
                          setForm({ ...form, tts_voice_id: vId });
                          if (vId) playAudioGreeting(form.tts_model, vId);
                        }
                      }}
                    >
                      <option value="" style={{ background: '#111' }}>Select Voice</option>
                      {ttsVoices.map((v) => (
                        <option key={v.id} value={v.id} style={{ background: '#111' }}>
                          {v.name}
                        </option>
                      ))}
                      <option value="__custom__" style={{ background: '#111', color: 'var(--accent-bright)' }}>
                        + Write custom voice ID...
                      </option>
                    </select>
                  ) : (
                    <input
                      className="glass-input"
                      placeholder="Enter custom ElevenLabs Voice ID"
                      value={form.tts_voice_id}
                      onChange={(e) => {
                        const val = e.target.value;
                        setForm((prev) => ({ ...prev, tts_voice_id: val }));
                        if (val.trim().length >= 4) {
                          playAudioGreeting(form.tts_model, val);
                        }
                      }}
                    />
                  )}
                </div>
              )}

              {playingAudio && (
                <p style={{ fontSize: '12px', color: 'var(--accent-bright)', margin: 0 }}>
                  🔊 Generating voice sample for {form.provider_type === 'deepgram' ? 'Deepgram' : 'ElevenLabs'} ("Hey, how's it going!")...
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
        )}
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
              Are you sure you want to remove this Speech provider? This action cannot be undone.
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
          <div className="section-hint__title">Speech Recognition (STT)</div>
          <div className="section-hint__body">
            Converts live streaming audio into accurate text transcripts in real-time.
          </div>
        </div>

        <div className="section-hint">
          <div className="section-hint__title">Speech Synthesis (TTS)</div>
          <div className="section-hint__body">
            Synthesizes realistic human-like voice responses from LLM token streams.
          </div>
        </div>

        <div className="section-hint">
          <div className="section-hint__title">Supported Engines</div>
          <div className="section-hint__body">
            Choose between Deepgram Nova-2/Aura and ElevenLabs Scribe/Flash models.
          </div>
        </div>
      </div>
    </div>
  );
}
