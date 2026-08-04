import { useState, useEffect } from "react";

const PROVIDER_CONFIGS = {
  llm: {
    types: [
      { value: "openai", label: "OpenAI" },
      { value: "anthropic", label: "Anthropic" },
      { value: "google", label: "Google" },
      { value: "openai_compatible", label: "OpenAI Compatible" },
    ],
    credFields: [{ key: "api_key", label: "API Key", type: "password" }],
    extraFields: [{ key: "base_url", label: "Base URL", type: "text" }],
  },
  speech: {
    types: [
      { value: "deepgram", label: "Deepgram" },
      { value: "elevenlabs", label: "ElevenLabs" },
    ],
    credFields: [{ key: "api_key", label: "API Key", type: "password" }],
  },
};

export default function ProviderManager() {
  const [tab, setTab] = useState("llm");
  const [llmProviders, setLlmProviders] = useState([]);
  const [speechProviders, setSpeechProviders] = useState([]);
  const [showForm, setShowForm] = useState(false);

  // LLM form
  const [llmForm, setLlmForm] = useState({ name: "", provider_type: "openai", base_url: "", credentials: { api_key: "" }, is_default: false });
  // Speech form
  const [speechForm, setSpeechForm] = useState({ name: "", provider_type: "deepgram", credentials: { api_key: "" }, stt_model: "", stt_language: "en", tts_model: "", tts_voice_id: "" });

  const load = () => {
    fetch("/admin/api/llm-providers").then((r) => r.json()).then(setLlmProviders).catch(console.error);
    fetch("/admin/api/speech-providers").then((r) => r.json()).then(setSpeechProviders).catch(console.error);
  };
  useEffect(load, []);

  const saveLLM = async () => {
    await fetch("/admin/api/llm-providers", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(llmForm) });
    setShowForm(false);
    setLlmForm({ name: "", provider_type: "openai", base_url: "", credentials: { api_key: "" }, is_default: false });
    load();
  };

  const saveSpeech = async () => {
    await fetch("/admin/api/speech-providers", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(speechForm) });
    setShowForm(false);
    setSpeechForm({ name: "", provider_type: "deepgram", credentials: { api_key: "" }, stt_model: "", stt_language: "en", tts_model: "", tts_voice_id: "" });
    load();
  };

  const removeLLM = async (id) => { await fetch(`/admin/api/llm-providers/${id}`, { method: "DELETE" }); load(); };
  const removeSpeech = async (id) => { await fetch(`/admin/api/speech-providers/${id}`, { method: "DELETE" }); load(); };

  return (
    <div>
      <h2 className="text-2xl font-bold text-white mb-8">Provider Manager</h2>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        {["llm", "speech"].map((t) => (
          <button key={t} onClick={() => { setTab(t); setShowForm(false); }}
            className={`px-6 py-2 rounded-xl text-sm font-medium transition-all ${tab === t ? "bg-cyan-500/20 border border-cyan-500/30 text-cyan-300" : "text-slate-400 border border-white/10 hover:bg-white/5"}`}>
            {t === "llm" ? "LLM Providers" : "Speech Providers"}
          </button>
        ))}
      </div>

      {/* Add button */}
      <button onClick={() => setShowForm(!showForm)} className="mb-6 px-6 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-violet-500 text-white text-sm font-medium hover:opacity-90 transition-opacity">
        + Add {tab === "llm" ? "LLM" : "Speech"} Provider
      </button>

      {/* LLM Form */}
      {showForm && tab === "llm" && (
        <div className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-6 mb-8">
          <h3 className="text-lg font-semibold text-white mb-4">Add LLM Provider</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <input className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none" placeholder="Provider Name" value={llmForm.name} onChange={(e) => setLlmForm({ ...llmForm, name: e.target.value })} />
            <select className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:border-cyan-500/50 focus:outline-none" value={llmForm.provider_type} onChange={(e) => setLlmForm({ ...llmForm, provider_type: e.target.value })}>
              {PROVIDER_CONFIGS.llm.types.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
            <input className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none" placeholder="Base URL (optional)" value={llmForm.base_url} onChange={(e) => setLlmForm({ ...llmForm, base_url: e.target.value })} />
            <input className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none" type="password" placeholder="API Key" value={llmForm.credentials.api_key} onChange={(e) => setLlmForm({ ...llmForm, credentials: { ...llmForm.credentials, api_key: e.target.value } })} />
          </div>
          <button onClick={saveLLM} className="mt-4 px-6 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-violet-500 text-white font-medium hover:opacity-90">Save</button>
        </div>
      )}

      {/* Speech Form */}
      {showForm && tab === "speech" && (
        <div className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-6 mb-8">
          <h3 className="text-lg font-semibold text-white mb-4">Add Speech Provider</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <input className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none" placeholder="Provider Name" value={speechForm.name} onChange={(e) => setSpeechForm({ ...speechForm, name: e.target.value })} />
            <select className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:border-cyan-500/50 focus:outline-none" value={speechForm.provider_type} onChange={(e) => setSpeechForm({ ...speechForm, provider_type: e.target.value })}>
              {PROVIDER_CONFIGS.speech.types.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
            <input className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none" type="password" placeholder="API Key" value={speechForm.credentials.api_key} onChange={(e) => setSpeechForm({ ...speechForm, credentials: { ...speechForm.credentials, api_key: e.target.value } })} />
            <input className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none" placeholder="STT Model" value={speechForm.stt_model} onChange={(e) => setSpeechForm({ ...speechForm, stt_model: e.target.value })} />
            <input className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none" placeholder="TTS Model" value={speechForm.tts_model} onChange={(e) => setSpeechForm({ ...speechForm, tts_model: e.target.value })} />
            <input className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none" placeholder="TTS Voice ID" value={speechForm.tts_voice_id} onChange={(e) => setSpeechForm({ ...speechForm, tts_voice_id: e.target.value })} />
          </div>
          <button onClick={saveSpeech} className="mt-4 px-6 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-violet-500 text-white font-medium hover:opacity-90">Save</button>
        </div>
      )}

      {/* Provider List */}
      <div className="space-y-4">
        {tab === "llm" && llmProviders.map((p) => (
          <div key={p.id} className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-6 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-violet-500/20 flex items-center justify-center text-xl">🧠</div>
              <div>
                <p className="text-white font-medium">{p.name}</p>
                <p className="text-slate-500 text-sm">{p.provider_type} {p.base_url ? `• ${p.base_url}` : ""}</p>
              </div>
            </div>
            <button onClick={() => removeLLM(p.id)} className="px-4 py-2 text-sm rounded-xl border border-red-500/30 text-red-400 hover:bg-red-500/10">Delete</button>
          </div>
        ))}
        {tab === "speech" && speechProviders.map((p) => (
          <div key={p.id} className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-6 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center text-xl">🔊</div>
              <div>
                <p className="text-white font-medium">{p.name}</p>
                <p className="text-slate-500 text-sm">{p.provider_type} • STT: {p.stt_model || "—"} • TTS: {p.tts_model || "—"}</p>
              </div>
            </div>
            <button onClick={() => removeSpeech(p.id)} className="px-4 py-2 text-sm rounded-xl border border-red-500/30 text-red-400 hover:bg-red-500/10">Delete</button>
          </div>
        ))}
        {((tab === "llm" && llmProviders.length === 0) || (tab === "speech" && speechProviders.length === 0)) && (
          <p className="text-slate-500 text-center py-12">No {tab === "llm" ? "LLM" : "speech"} providers configured</p>
        )}
      </div>
    </div>
  );
}
