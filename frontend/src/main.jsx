import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

// Admin API authentication interceptor
const originalFetch = window.fetch;
window.fetch = async (input, init = {}) => {
  const url = typeof input === "string" ? input : input?.url || "";
  if (url.includes("/admin/api")) {
    const adminKey = sessionStorage.getItem("admin_api_key") || sessionStorage.getItem("widtts_admin_key") || "admin-dev-key";
    const headers = new Headers(init.headers || (typeof input === "object" && input.headers ? input.headers : {}));
    if (!headers.has("X-Admin-Key") && !headers.has("Authorization")) {
      headers.set("X-Admin-Key", adminKey);
    }
    init = { ...init, headers };
  }
  return originalFetch(input, init);
};

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
