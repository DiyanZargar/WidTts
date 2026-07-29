import { ConversationProvider } from "./context/ConversationContext";
import HomePage from "./pages/HomePage";

export default function App() {
  return (
    <ConversationProvider>
      <HomePage />
    </ConversationProvider>
  );
}
