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
    case "CLOSE_WIDGET":
      return { ...initialState, isOpen: false };
    case "SESSION_STARTED":
      return { ...state, status: "active", sessionId: action.sessionId, isListening: true };
    case "SET_LISTENING":
      return { ...state, isListening: action.value };
    case "APPEND_TRANSCRIPT_LINE":
      // Avoid duplicate adjacent lines if identical text arrived
      const existing = state.transcriptLines;
      const lastLine = existing[existing.length - 1];
      if (lastLine && lastLine.speaker === action.line.speaker && lastLine.text === action.line.text) {
        return state;
      }
      return {
        ...state,
        transcriptLines: [...existing.slice(-50), action.line],
        partialTranscript: action.line.speaker === "user" ? "" : state.partialTranscript,
        partialAssistantTranscript: action.line.speaker === "assistant" ? "" : state.partialAssistantTranscript,
      };
    case "SET_PARTIAL_TRANSCRIPT":
      return { ...state, partialTranscript: action.text };
    case "CLEAR_PARTIAL_TRANSCRIPT":
      return { ...state, partialTranscript: "" };
    case "SET_PARTIAL_ASSISTANT_TRANSCRIPT":
      return { ...state, partialAssistantTranscript: action.text };
    case "CLEAR_PARTIAL_ASSISTANT_TRANSCRIPT":
      return { ...state, partialAssistantTranscript: "" };
    case "SET_ASSISTANT_HIGHLIGHT":
      return { ...state, isSpeaking: action.value };
    case "SESSION_COMPLETED":
      return { ...state, status: "completed", isSpeaking: false, isListening: false };
    case "RESET_FOR_NEW_SESSION":
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
