import { createContext, useReducer } from "react";

const initialState = {
  isOpen: false,
  sessionId: null,
  status: "idle",
  transcriptLines: [],
  partialTranscript: "",
  isSpeaking: false,
  isListening: false,
};

function reducer(state, action) {
  switch (action.type) {
    case "OPEN_WIDGET":
      return { ...state, isOpen: true };
    case "CLOSE_WIDGET":
      return { ...initialState, isOpen: false };
    case "SESSION_STARTED":
      return { ...state, status: "active", sessionId: action.sessionId, isListening: true };
    case "SET_LISTENING":
      return { ...state, isListening: action.value };
    case "RECOVER_TRANSCRIPT":
      return {
        ...state,
        transcriptLines: action.messages.map((m, i) => ({
          id: i,
          speaker: m.sender === "system" ? "assistant" : "user",
          text: m.text,
          isHighlighted: false,
        })),
      };
    case "APPEND_TRANSCRIPT_LINE":
      return {
        ...state,
        transcriptLines: [...state.transcriptLines.slice(-5), action.line],
      };
    case "SET_PARTIAL_TRANSCRIPT":
      return { ...state, partialTranscript: action.text };
    case "CLEAR_PARTIAL_TRANSCRIPT":
      return { ...state, partialTranscript: "" };
    case "SET_ASSISTANT_HIGHLIGHT":
      return { ...state, isSpeaking: action.value };
    case "SESSION_COMPLETED":
      return { ...state, status: "completed", isSpeaking: false, isListening: false };
    case "SESSION_CANCELLED":
      return { ...state, status: "cancelled", isSpeaking: false, isListening: false };
    case "RESET_FOR_NEW_SESSION":
      return { ...initialState, isOpen: true };
    case "SESSION_RESET":
      return { ...initialState, isOpen: true };
    default:
      return state;
  }
}

export const ConversationContext = createContext(null);

export function ConversationProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  return (
    <ConversationContext.Provider value={{ state, dispatch }}>
      {children}
    </ConversationContext.Provider>
  );
}
