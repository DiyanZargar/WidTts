import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ConversationProvider } from "./context/ConversationContext";
import HomePage from "./pages/HomePage";

// Lazy load 3D Admin Journey so user portal stays ultra-lightweight
const AdminJourney = lazy(() =>
  import("./components/journey/AdminJourney").then((m) => ({ default: m.AdminJourney }))
);

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Bot direct voice session route — opens directly with Connect */}
        <Route
          path="/bot/:slug"
          element={
            <ConversationProvider>
              <HomePage />
            </ConversationProvider>
          }
        />
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
        <Route
          path="*"
          element={
            <Suspense
              fallback={
                <div
                  style={{
                    width: "100vw",
                    height: "100vh",
                    background: "#050507",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                />
              }
            >
              <AdminJourney />
            </Suspense>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
