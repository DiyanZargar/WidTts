export function createConversationSocket({ conversationType, sessionId, onEvent, onAudio }) {
  const baseUrl = import.meta.env.VITE_WS_BASE_URL || "";
  let url = `${baseUrl}/ws/${conversationType}`;
  if (sessionId) {
    url += `?session_id=${sessionId}`;
  }
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
    sendJson: (obj) => {
      if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(obj));
    },
    close: () => socket.close(),
  };
}
