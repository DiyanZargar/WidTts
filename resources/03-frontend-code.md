# Frontend Implementation (React, WebSocket, Deepgram audio I/O)

The frontend is the Presentation layer for browser-side concerns. Its
structure (components, hooks, services, context, pages, utils) is
appropriate for a React application. The backend's Modular Monolith +
Clean Architecture boundary is enforced server-side; the frontend
communicates with the backend exclusively through a single WebSocket
entrypoint and does not depend on backend internal module structure.

## context/ConversationContext.jsx

```jsx
import { createContext, useReducer } from "react";

const initialState = {
  isOpen: false,
  sessionId: null,
  status: "idle", // idle | connecting | active | completed | cancelled
  transcript: [], // { sender: 'system'|'user', text: string }
  isSpeaking: false,
  isListening: false,
};

function reducer(state, action) {
  switch (action.type) {
    case "OPEN_WIDGET":
      return { ...state, isOpen: true };
    case "CLOSE_WIDGET":
      return { ...state, isOpen: false };
    case "SESSION_STARTED":
      return { ...state, status: "active", sessionId: action.sessionId };
    case "ADD_MESSAGE":
      return { ...state, transcript: [...state.transcript, action.message] };
    case "SET_SPEAKING":
      return { ...state, isSpeaking: action.value };
    case "SET_LISTENING":
      return { ...state, isListening: action.value };
    case "SESSION_COMPLETED":
      return { ...state, status: "completed", isSpeaking: false, isListening: false };
    case "SESSION_CANCELLED":
      return { ...state, status: "cancelled", isSpeaking: false, isListening: false };
    case "RESET_FOR_NEW_SESSION":
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
```

## utils/audioUtils.js

```javascript
export function createMicStream(onChunk) {
  return navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
    const recorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) e.data.arrayBuffer().then(onChunk);
    };
    recorder.start(250); // 250ms chunks, streaming, no polling
    return { recorder, stream };
  });
}

export function stopMicStream({ recorder, stream }) {
  recorder.stop();
  stream.getTracks().forEach((t) => t.stop());
}

export function playAudioBuffer(arrayBuffer, audioContext) {
  return audioContext.decodeAudioData(arrayBuffer.slice(0)).then((decoded) => {
    const source = audioContext.createBufferSource();
    source.buffer = decoded;
    source.connect(audioContext.destination);
    source.start(0);
    return source; // caller keeps reference to allow .stop() on barge-in
  });
}
```

## services/websocketService.js

```javascript
export function createConversationSocket({ conversationType, sessionId, onEvent, onAudio }) {
  const url = `${import.meta.env.VITE_WS_BASE_URL}/ws/${conversationType}/${sessionId}`;
  const socket = new WebSocket(url);
  socket.binaryType = "arraybuffer";

  socket.onmessage = (msg) => {
    if (typeof msg.data === "string") {
      onEvent(JSON.parse(msg.data));
    } else {
      onAudio(msg.data);
    }
  };

  return {
    socket,
    sendAudioChunk: (buffer) => {
      if (socket.readyState === WebSocket.OPEN) socket.send(buffer);
    },
    close: () => socket.close(),
  };
}
```

## hooks/useDeepgramAudio.js

```javascript
import { useRef, useCallback } from "react";
import { createMicStream, stopMicStream, playAudioBuffer } from "../utils/audioUtils";

export function useDeepgramAudio() {
  const micRef = useRef(null);
  const audioContextRef = useRef(null);
  const currentSourceRef = useRef(null);

  const getAudioContext = () => {
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
    }
    return audioContextRef.current;
  };

  const startMic = useCallback(async (onChunk) => {
    micRef.current = await createMicStream(onChunk);
  }, []);

  const stopMic = useCallback(() => {
    if (micRef.current) {
      stopMicStream(micRef.current);
      micRef.current = null;
    }
  }, []);

  const playTTS = useCallback(async (arrayBuffer) => {
    const source = await playAudioBuffer(arrayBuffer, getAudioContext());
    currentSourceRef.current = source;
    return new Promise((resolve) => {
      source.onended = resolve;
    });
  }, []);

  const stopTTS = useCallback(() => {
    if (currentSourceRef.current) {
      try {
        currentSourceRef.current.stop();
      } catch (_) {}
      currentSourceRef.current = null;
    }
  }, []);

  return { startMic, stopMic, playTTS, stopTTS };
}
```

## hooks/useWebSocket.js

```javascript
import { useRef, useContext, useCallback } from "react";
import { ConversationContext } from "../context/ConversationContext";
import { createConversationSocket } from "../services/websocketService";
import { useDeepgramAudio } from "./useDeepgramAudio";

export function useWebSocket(conversationType) {
  const { state, dispatch } = useContext(ConversationContext);
  const connRef = useRef(null);
  const { startMic, stopMic, playTTS, stopTTS } = useDeepgramAudio();

  const connect = useCallback(() => {
    let sessionId = sessionStorage.getItem("widget_session_id");
    if (!sessionId || state.status === "completed" || state.status === "cancelled") {
      sessionId = crypto.randomUUID();
      sessionStorage.setItem("widget_session_id", sessionId);
      dispatch({ type: "RESET_FOR_NEW_SESSION" });
    }

    const onEvent = (evt) => {
      switch (evt.event) {
        case "session_started":
          dispatch({ type: "SESSION_STARTED", sessionId: evt.payload.session_id });
          break;
        case "question":
        case "instruction":
          dispatch({ type: "ADD_MESSAGE", message: { sender: "system", text: evt.payload.text } });
          break;
        case "tts_audio_meta":
          dispatch({ type: "SET_SPEAKING", value: true });
          break;
        case "tts_stop":
          stopTTS();
          dispatch({ type: "SET_SPEAKING", value: false });
          break;
        case "validation_result":
          break;
        case "session_completed":
          stopMic();
          dispatch({ type: "SESSION_COMPLETED" });
          break;
        case "session_cancelled":
          stopMic();
          dispatch({ type: "SESSION_CANCELLED" });
          break;
        case "error":
          console.error(evt.payload.message);
          break;
        default:
          break;
      }
    };

    const onAudio = async (arrayBuffer) => {
      dispatch({ type: "SET_SPEAKING", value: true });
      await playTTS(arrayBuffer);
      dispatch({ type: "SET_SPEAKING", value: false });
      dispatch({ type: "SET_LISTENING", value: true });
    };

    connRef.current = createConversationSocket({ conversationType, sessionId, onEvent, onAudio });

    startMic((chunk) => {
      connRef.current.sendAudioChunk(chunk);
    });
  }, [conversationType, dispatch, playTTS, startMic, state.status, stopMic, stopTTS]);

  const disconnect = useCallback(() => {
    stopMic();
    stopTTS();
    connRef.current?.close();
  }, [stopMic, stopTTS]);

  return { connect, disconnect };
}
```

## components/WidgetButton.jsx

```jsx
import { useContext } from "react";
import { ConversationContext } from "../context/ConversationContext";

export default function WidgetButton() {
  const { dispatch } = useContext(ConversationContext);
  return (
    <button onClick={() => dispatch({ type: "OPEN_WIDGET" })} aria-label="Open assistant">
      Talk to Assistant
    </button>
  );
}
```

## components/Transcript.jsx

```jsx
import { useContext } from "react";
import { ConversationContext } from "../context/ConversationContext";

export default function Transcript() {
  const { state } = useContext(ConversationContext);
  return (
    <div className="transcript">
      {state.transcript.map((m, i) => (
        <div key={i} className={`transcript-line ${m.sender}`}>
          <strong>{m.sender === "system" ? "Assistant" : "You"}:</strong> {m.text}
        </div>
      ))}
    </div>
  );
}
```

## components/SpeakingIndicator.jsx

```jsx
import { useContext } from "react";
import { ConversationContext } from "../context/ConversationContext";

export default function SpeakingIndicator() {
  const { state } = useContext(ConversationContext);
  if (!state.isSpeaking) return null;
  return <div className="speaking-indicator">Assistant is speaking…</div>;
}
```

## components/ListeningIndicator.jsx

```jsx
import { useContext } from "react";
import { ConversationContext } from "../context/ConversationContext";

export default function ListeningIndicator() {
  const { state } = useContext(ConversationContext);
  if (!state.isListening) return null;
  return <div className="listening-indicator">Listening…</div>;
}
```

## components/SessionEndedState.jsx

```jsx
import { useContext } from "react";
import { ConversationContext } from "../context/ConversationContext";

export default function SessionEndedState() {
  const { state, dispatch } = useContext(ConversationContext);
  if (state.status !== "completed" && state.status !== "cancelled") return null;
  return (
    <div className="session-ended">
      <p>{state.status === "completed" ? "Session complete." : "Session cancelled."}</p>
      <button onClick={() => dispatch({ type: "CLOSE_WIDGET" })}>Close</button>
    </div>
  );
}
```

## components/ConversationWindow.jsx

```jsx
import { useContext, useEffect } from "react";
import { ConversationContext } from "../context/ConversationContext";
import { useWebSocket } from "../hooks/useWebSocket";
import Transcript from "./Transcript";
import SpeakingIndicator from "./SpeakingIndicator";
import ListeningIndicator from "./ListeningIndicator";
import SessionEndedState from "./SessionEndedState";

export default function ConversationWindow({ conversationType = "daily_life_companion" }) {
  const { state } = useContext(ConversationContext);
  const { connect, disconnect } = useWebSocket(conversationType);

  useEffect(() => {
    if (state.isOpen && state.status === "idle") connect();
    return () => {
      if (!state.isOpen) disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.isOpen]);

  if (!state.isOpen) return null;

  return (
    <div className="conversation-window">
      <Transcript />
      <SpeakingIndicator />
      <ListeningIndicator />
      <SessionEndedState />
    </div>
  );
}
```

## pages/HomePage.jsx

```jsx
import WidgetButton from "../components/WidgetButton";
import ConversationWindow from "../components/ConversationWindow";

export default function HomePage() {
  return (
    <main>
      <h1>Site Content</h1>
      <WidgetButton />
      <ConversationWindow conversationType="daily_life_companion" />
    </main>
  );
}
```

## App.jsx

```jsx
import { ConversationProvider } from "./context/ConversationContext";
import HomePage from "./pages/HomePage";

export default function App() {
  return (
    <ConversationProvider>
      <HomePage />
    </ConversationProvider>
  );
}
```
