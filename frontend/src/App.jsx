import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ConversationProvider } from "./context/ConversationContext";
import HomePage from "./pages/HomePage";
import BotLanding from "./pages/BotLanding";
import { AdminJourney } from "./components/journey/AdminJourney";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Bot deploy links — user-facing landing + session */}
        <Route path="/bot/:slug" element={<BotLanding />} />
        <Route
          path="/bot/:slug/session"
          element={
            <ConversationProvider>
              <HomePage />
            </ConversationProvider>
          }
        />

        {/* Legacy /user route — redirects handled by HomePage */}
        <Route
          path="/user"
          element={
            <ConversationProvider>
              <HomePage />
            </ConversationProvider>
          }
        />

        {/* Everything else → the journey (gate + admin scroll experience) */}
        <Route path="*" element={<AdminJourney />} />
      </Routes>
    </BrowserRouter>
  );
}
