"""LiveKit Session Adapter. Manages the full lifecycle of an agent session
in a LiveKit room — building STT/TTS plugins, the LLM bridge, and the
AgentSession, then tearing everything down on destroy."""
import logging
import time
from typing import Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger("livekit_session")

from app.shared.logging import pipeline_logger as pl


@dataclass
class SessionSnapshot:
    session_id: str
    bot_id: str
    bot_name: str
    system_prompt: str
    # STT provider (can be different from TTS)
    stt_provider_type: str
    stt_model: str
    # TTS provider (can be different from STT)
    tts_provider_type: str
    tts_model: str
    tts_voice_id: str
    # LLM
    llm_provider_id: str
    llm_model: str
    # LiveKit
    server_url: str
    room_name: str
    audio_sample_rate: int
    llm_api_key: str = ""
    llm_base_url: str = ""
    # Encrypted credentials (blob + key_version) — factory decrypts
    encrypted_stt_credentials: dict = field(default_factory=dict)
    stt_key_version: int = 0
    encrypted_tts_credentials: dict = field(default_factory=dict)
    tts_key_version: int = 0


@dataclass
class LiveKitSession:
    snapshot: SessionSnapshot
    _stt_plugin: Any = field(default=None, repr=False)
    _tts_plugin: Any = field(default=None, repr=False)
    _vad_plugin: Any = field(default=None, repr=False)
    _llm_bridge: Any = field(default=None, repr=False)
    _agent_session: Any = field(default=None, repr=False)
    _room: Any = field(default=None, repr=False)
    _is_destroyed: bool = False
    _started_at: Optional[float] = None

    async def start(self, room) -> None:
        self._started_at = time.monotonic()
        self._room = room
        logger.info(
            "[SESSION] Starting session=%s bot=%s room=%s",
            self.snapshot.session_id, self.snapshot.bot_name, self.snapshot.room_name,
        )
        try:
            from livekit.agents import AgentSession, Agent
            from livekit.agents.voice.room_io import RoomOptions, TextOutputOptions
            from livekit.plugins import silero

            self._stt_plugin = await self._build_stt()
            self._tts_plugin = await self._build_tts()
            self._llm_bridge = self._build_llm_bridge()
            self._vad_plugin = silero.VAD.load(
                min_silence_duration=0.4,
                activation_threshold=0.45,
                min_speech_duration=0.05,
            )
            import os
            timeout_sec = float(os.getenv("ROOM_INACTIVITY_TIMEOUT_SECONDS", "30"))

            self._agent_session = AgentSession(
                vad=self._vad_plugin,
                stt=self._stt_plugin,
                llm=self._llm_bridge,
                tts=self._tts_plugin,
                user_away_timeout=timeout_sec,
            )

            # Handle inactivity timeout (user away for timeout_sec)
            @self._agent_session.on("user_state_changed")
            def _on_user_state_changed(ev):
                if getattr(ev, "new_state", None) == "away":
                    logger.info("[SESSION] Inactivity timeout (%ss) reached for session=%s", timeout_sec, self.snapshot.session_id)
                    import asyncio
                    async def _disconnect_inactivity():
                        try:
                            if self._agent_session and self._agent_session.room:
                                import json
                                payload = json.dumps({"event": "session_end", "payload": {"reason": "inactivity_timeout"}}).encode('utf-8')
                                await self._agent_session.room.local_participant.publish_data(payload)
                        except Exception:
                            pass
                        await self.destroy()
                    asyncio.create_task(_disconnect_inactivity())

            agent = Agent(instructions=self.snapshot.system_prompt)
            await self._agent_session.start(
                room=room,
                agent=agent,
                room_options=RoomOptions(
                    text_output=TextOutputOptions(sync_transcription=False),
                ),
            )

            # Speak initial greeting immediately when the room connects
            await self._agent_session.say("Hi there! What should I call you?")

            duration_ms = int((time.monotonic() - self._started_at) * 1000)
            logger.info(
                "[SESSION] AgentSession started in %dms session=%s",
                duration_ms, self.snapshot.session_id,
            )
            pl.session_start(
                session_id=self.snapshot.session_id,
                conversation_type="voice",
                is_recovery=False,
            )
        except Exception as e:
            logger.error("[SESSION] Failed to start: %s", e)
            await self.destroy()
            raise

    # ------------------------------------------------------------------
    # Plugin builders
    # ------------------------------------------------------------------

    async def _build_stt(self):
        """Build STT plugin via the module-level factory function."""
        from app.modules.voice.infrastructure.external.speech_plugin_factory import (
            build_stt_plugin,
        )

        config = {
            "provider_type": self.snapshot.stt_provider_type,
            "stt_model": self.snapshot.stt_model,
            "credentials_enc": self.snapshot.encrypted_stt_credentials,
            "key_version": self.snapshot.stt_key_version,
        }
        return await build_stt_plugin(config)

    async def _build_tts(self):
        """Build TTS plugin via the module-level factory function."""
        from app.modules.voice.infrastructure.external.speech_plugin_factory import (
            build_tts_plugin,
        )

        config = {
            "provider_type": self.snapshot.tts_provider_type,
            "tts_model": self.snapshot.tts_model,
            "tts_voice_id": self.snapshot.tts_voice_id,
            "credentials_enc": self.snapshot.encrypted_tts_credentials,
            "key_version": self.snapshot.tts_key_version,
        }
        return await build_tts_plugin(config)

    def _build_llm_bridge(self):
        """Build the LLM bridge with a conversation adapter and full credentials."""
        from app.modules.voice.infrastructure.external.widtts_llm_bridge import (
            WidTTSLLMBridge,
            DefaultConversationAdapter,
        )
        from app.modules.conversation.domain.policy.conversation_policy import (
            ConversationPolicy,
        )

        llm_config = {
            "api_key": self.snapshot.llm_api_key,
            "base_url": self.snapshot.llm_base_url,
            "model": self.snapshot.llm_model,
        }
        conversation_adapter = DefaultConversationAdapter(llm_config)

        policy = ConversationPolicy()
        bot_config = {
            "system_prompt": self.snapshot.system_prompt,
            "llm_model": self.snapshot.llm_model,
            "llm_provider_id": self.snapshot.llm_provider_id,
            "api_key": self.snapshot.llm_api_key,
            "base_url": self.snapshot.llm_base_url,
        }
        return WidTTSLLMBridge(
            bot=bot_config,
            policy=policy,
            conversation_adapter=conversation_adapter,
        )

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------

    async def destroy(self) -> None:
        if self._is_destroyed:
            return
        self._is_destroyed = True
        logger.info("[SESSION] Destroying session=%s", self.snapshot.session_id)

        if self._agent_session:
            try:
                await self._agent_session.aclose()
            except Exception as e:
                logger.warning("[SESSION] AgentSession close error: %s", e)
            self._agent_session = None

        for plugin_name, plugin in [
            ("stt", self._stt_plugin),
            ("tts", self._tts_plugin),
            ("vad", self._vad_plugin),
        ]:
            if plugin:
                try:
                    if hasattr(plugin, "aclose"):
                        await plugin.aclose()
                    elif hasattr(plugin, "close"):
                        await plugin.close()
                except Exception as e:
                    logger.warning("[SESSION] %s close error: %s", plugin_name, e)

        self._stt_plugin = None
        self._tts_plugin = None
        self._vad_plugin = None
        self._llm_bridge = None
        self._room = None
        logger.info("[SESSION] Session destroyed: %s", self.snapshot.session_id)
        pl.session_end(session_id=self.snapshot.session_id, reason="session_destroyed")

    @property
    def is_destroyed(self) -> bool:
        return self._is_destroyed
