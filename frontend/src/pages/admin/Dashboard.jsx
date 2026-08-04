import { useState, useEffect } from "react";
import { Admin3DCanvas } from "../../components/3d/Admin3DCanvas";

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);

  useEffect(() => {
    Promise.all([
      fetch("/admin/api/runtime/stats").then((r) => r.json()),
      fetch("/admin/api/runtime/health").then((r) => r.json()),
    ]).then(([s, h]) => {
      setStats(s);
      setHealth(h);
    }).catch(console.error);
  }, []);

  const StatCard = ({ label, value, color = "cyan" }) => (
    <div className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-6 hover:border-cyan-500/30 transition-all duration-300">
      <p className="text-sm font-medium text-slate-400">{label}</p>
      <p className={`text-3xl font-bold mt-2 text-${color}-400`}>
        {value ?? "—"}
      </p>
    </div>
  );

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-white tracking-tight">3D Command Center</h2>
          <p className="text-sm text-slate-400 mt-1">Platform metrics & 3D holographic avatar core</p>
        </div>

        {/* Database Health Badge */}
        <div className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-xl px-4 py-2 flex items-center gap-3">
          <div
            className={`w-3 h-3 rounded-full ${
              health?.status === "ok" ? "bg-emerald-400 animate-pulse shadow-lg shadow-emerald-500/50" : "bg-red-500"
            }`}
          />
          <span className="text-slate-300 text-xs font-semibold uppercase tracking-wider">
            DB: {health?.status === "ok" ? "Connected" : "Disconnected"}
          </span>
        </div>
      </div>

      {/* 3D Holographic Core Canvas */}
      <Admin3DCanvas
        activeBot={stats?.active_bot}
        isListening={stats?.active_sessions > 0}
      />

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard label="Configured Bots" value={stats?.bots} color="cyan" />
        <StatCard label="LLM Providers" value={stats?.llm_providers} color="violet" />
        <StatCard label="Speech Providers" value={stats?.speech_providers} color="amber" />
        <StatCard label="Active Sessions" value={stats?.active_sessions} color="emerald" />
      </div>

      {/* Active Bot Overview Card */}
      <div className="backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl p-6 relative overflow-hidden">
        <div className="absolute -top-12 -right-12 w-40 h-40 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none"></div>
        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <span>🤖</span> Active Bot Instance
        </h3>
        {stats?.active_bot ? (
          <div className="flex items-center justify-between p-4 rounded-xl bg-cyan-500/10 border border-cyan-500/30">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cyan-500 to-violet-500 flex items-center justify-center text-2xl shadow-lg shadow-cyan-500/20">
                🤖
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-white font-semibold text-lg">{stats.active_bot.name}</p>
                  <span className="text-xs px-2.5 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-mono">
                    ACTIVE
                  </span>
                </div>
                <p className="text-slate-400 text-xs font-mono mt-0.5">ID: {stats.active_bot.id}</p>
              </div>
            </div>
          </div>
        ) : (
          <div className="p-6 text-center border border-dashed border-white/10 rounded-xl">
            <p className="text-slate-400 text-sm">No active bot configured</p>
            <p className="text-slate-500 text-xs mt-1">Go to Bots manager to activate a bot</p>
          </div>
        )}
      </div>
    </div>
  );
}
