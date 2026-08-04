import { useState, useEffect } from "react";
import { Routes, Route, NavLink, useNavigate } from "react-router-dom";
import BotManager from "./BotManager";
import ProviderManager from "./ProviderManager";
import Dashboard from "./Dashboard";

const NAV_ITEMS = [
  { path: "", label: "Dashboard", icon: "📊" },
  { path: "bots", label: "Bots", icon: "🤖" },
  { path: "providers", label: "Providers", icon: "🔌" },
];

export default function AdminLayout() {
  const navigate = useNavigate();

  useEffect(() => {
    const role = sessionStorage.getItem("widtts_role");
    if (role !== "admin") {
      navigate("/login");
    }
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-950 flex">
      {/* Sidebar */}
      <aside className="w-64 border-r border-white/10 backdrop-blur-xl bg-white/5 p-6 flex flex-col">
        <div className="mb-8">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 to-violet-400 bg-clip-text text-transparent">
            widTTS
          </h1>
          <p className="text-xs text-slate-500 mt-1">Admin Portal</p>
        </div>

        <nav className="space-y-2 flex-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.path}
              to={`/admin/${item.path}`}
              end={item.path === ""}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? "bg-cyan-500/20 border border-cyan-500/30 text-cyan-300"
                    : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                }`
              }
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <button
          onClick={() => {
            sessionStorage.removeItem("widtts_role");
            navigate("/login");
          }}
          className="mt-auto px-4 py-2 text-sm text-slate-500 hover:text-red-400 transition-colors"
        >
          ← Logout
        </button>
      </aside>

      {/* Main content */}
      <main className="flex-1 p-8 overflow-y-auto">
        <Routes>
          <Route index element={<Dashboard />} />
          <Route path="bots" element={<BotManager />} />
          <Route path="providers" element={<ProviderManager />} />
        </Routes>
      </main>
    </div>
  );
}
