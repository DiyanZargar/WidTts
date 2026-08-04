import { useState, useEffect } from "react";

export default function BotManager() {
  const [bots, setBots] = useState([]);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: "", description: "", personality: "", system_prompt: "", llm_provider_id: "", llm_model: "", speech_provider_id: "" });
  const [llmProviders, setLlmProviders] = useState([]);
  const [speechProviders, setSpeechProviders] = useState([]);

  const load = () => {
    fetch("/admin/api/bots").then((r) => r.json()).then(setBots).catch(console.error);
    fetch("/admin/api/llm-providers").then((r) => r.json()).then(setLlmProviders).catch(console.error);
    fetch("/admin/api/speech-providers").then((r) => r.json()).then(setSpeechProviders).catch(console.error);
  };
  useEffect(load, []);

  const save = async () => {
    const body = { ...form };
    if (editing) {
      await fetch(`/admin/api/bots/${editing}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    } else {
      await fetch("/admin/api/bots", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    }
    setEditing(null);
    setForm({ name: "", description: "", personality: "", system_prompt: "", llm_provider_id: "", llm_model: "", speech_provider_id: "" });
    load();
  };

  const activate = async (id) => {
    await fetch(`/admin/api/bots/${id}/activate`, { method: "POST" });
    load();
  };

  const remove = async (id) => {
    await fetch(`/admin/api/bots/${id}`, { method: "DELETE" });
    load();
  };

  const edit = (bot) => {
    setEditing(bot.id);
    setForm({
      name: bot.name, description: bot.description || "", personality: bot.personality || "",
      system_prompt: bot.system_prompt || "", llm_provider_id: bot.llm_provider_id || "",
      llm_model: bot.llm_model || "", speech_provider_id: bot.speech_provider_id || "",
    });
  };

  return (
    <div>
      <h2 className="text-2xl font-bold text-white mb-8">Bot Manager</h2>

      {/* Form */}
      <div className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-6 mb-8">
        <h3 className="text-lg font-semibold text-white mb-4">{editing ? "Edit Bot" : "Create Bot"}</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <input className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none" placeholder="Bot Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none" placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <input className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none" placeholder="Greeting / Personality line" value={form.personality} onChange={(e) => setForm({ ...form, personality: e.target.value })} />
          <input className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none" placeholder="LLM Model (e.g. gpt-4o-mini)" value={form.llm_model} onChange={(e) => setForm({ ...form, llm_model: e.target.value })} />
          <select className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:border-cyan-500/50 focus:outline-none" value={form.llm_provider_id} onChange={(e) => setForm({ ...form, llm_provider_id: e.target.value })}>
            <option value="">Select LLM Provider</option>
            {llmProviders.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.provider_type})</option>)}
          </select>
          <select className="bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:border-cyan-500/50 focus:outline-none" value={form.speech_provider_id} onChange={(e) => setForm({ ...form, speech_provider_id: e.target.value })}>
            <option value="">Select Speech Provider</option>
            {speechProviders.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.provider_type})</option>)}
          </select>
        </div>
        <div className="mt-4">
          <textarea className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none min-h-[200px] font-mono text-sm" placeholder="System Prompt — This drives ALL LLM behavior: interview logic, conversation flow, personality, response format..." value={form.system_prompt} onChange={(e) => setForm({ ...form, system_prompt: e.target.value })} />
        </div>
        <div className="flex gap-3 mt-4">
          <button onClick={save} className="px-6 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-violet-500 text-white font-medium hover:opacity-90 transition-opacity">{editing ? "Update" : "Create"}</button>
          {editing && <button onClick={() => { setEditing(null); setForm({ name: "", description: "", personality: "", system_prompt: "", llm_provider_id: "", llm_model: "", speech_provider_id: "" }); }} className="px-6 py-2 rounded-xl border border-white/10 text-slate-400 hover:text-white transition-colors">Cancel</button>}
        </div>
      </div>

      {/* Bot List */}
      <div className="space-y-4">
        {bots.map((bot) => (
          <div key={bot.id} className={`backdrop-blur-xl border rounded-2xl p-6 flex items-center justify-between ${bot.is_active ? "bg-cyan-500/10 border-cyan-500/30" : "bg-white/5 border-white/10"}`}>
            <div className="flex items-center gap-4">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-xl ${bot.is_active ? "bg-cyan-500/20" : "bg-white/5"}`}>
                🤖
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-white font-medium">{bot.name}</p>
                  {bot.is_active && <span className="text-xs px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">ACTIVE</span>}
                </div>
                <p className="text-slate-500 text-sm">{bot.description || "No description"}</p>
              </div>
            </div>
            <div className="flex gap-2">
              {!bot.is_active && <button onClick={() => activate(bot.id)} className="px-4 py-2 text-sm rounded-xl border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 transition-colors">Activate</button>}
              <button onClick={() => edit(bot)} className="px-4 py-2 text-sm rounded-xl border border-white/10 text-slate-400 hover:text-white transition-colors">Edit</button>
              <button onClick={() => remove(bot.id)} className="px-4 py-2 text-sm rounded-xl border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors">Delete</button>
            </div>
          </div>
        ))}
        {bots.length === 0 && <p className="text-slate-500 text-center py-12">No bots created yet</p>}
      </div>
    </div>
  );
}
