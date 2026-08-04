import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ConversationProvider } from "./context/ConversationContext";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import AdminLayout from "./pages/admin/AdminLayout";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Login */}
        <Route path="/login" element={<LoginPage />} />

        {/* User portal — existing voice UI */}
        <Route
          path="/user"
          element={
            <ConversationProvider>
              <HomePage />
            </ConversationProvider>
          }
        />

        {/* Admin portal */}
        <Route path="/admin/*" element={<AdminLayout />} />

        {/* Default redirect → user portal */}
        <Route path="/" element={<Navigate to="/user" replace />} />
        <Route path="*" element={<Navigate to="/user" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
