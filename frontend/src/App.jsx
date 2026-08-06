import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ConversationProvider } from "./context/ConversationContext";
import HomePage from "./pages/HomePage";
import { AdminJourney } from "./components/journey/AdminJourney";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* User portal — redesigned single-screen voice experience */}
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
