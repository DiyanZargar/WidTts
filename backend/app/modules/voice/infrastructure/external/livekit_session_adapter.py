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
    bot_description: str = ""
    system_prompt: str = ""
    stt_provider_type: str = ""
    stt_model: str = ""
    tts_provider_type: str = ""
    tts_model: str = ""
    llm_provider_id: str = ""
    llm_model: str = ""
    server_url: str = ""
    room_name: str = ""
    audio_sample_rate: int = 16000
    # Fields with defaults
    greeting: str = ""
    stt_language: str = "en"
    tts_voice_id: str = ""
    tts_language: str = "en"
    tts_custom_model: str = ""
    tts_custom_voice_id: str = ""
    tts_custom_endpoint: str = ""
    stt_languages: list = field(default_factory=lambda: ["en"])
    stt_primary_language: str = "en"
    tts_languages: list = field(default_factory=lambda: ["en"])
    tts_primary_language: str = "en"
    llm_api_key: str = ""
    llm_base_url: str = ""
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
            from app.shared.config.settings import settings
            timeout_sec = settings.room_inactivity_timeout_seconds

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

            # Build system instructions with bot identity and language
            bot_name = self.snapshot.bot_name or "Assistant"
            bot_desc = self.snapshot.bot_description or ""
            lang = self.snapshot.tts_primary_language or "en"
            identity = f"Your name is \"{bot_name}\". You MUST use this name when introducing yourself — never invent, guess, or substitute a different name."
            if bot_desc:
                identity += f" {bot_desc}"
            if lang and lang != "en":
                identity += (
                    f" You MUST ALWAYS respond in language '{lang}' and no other language."
                    f" This is non-negotiable — every response, every word, must be in '{lang}'."
                    f" When you need to end the conversation or say goodbye, append the marker [END_SESSION] at the very end of your response."
                )
            else:
                identity += " When you need to end the conversation or say goodbye, append the marker [END_SESSION] at the very end of your response."
            instructions = f"{identity}\n\n{self.snapshot.system_prompt}" if self.snapshot.system_prompt else identity

            # Default behavioral guidelines — these complement the user's system prompt.
            # They only apply when the user's prompt does not specify otherwise.
            _default_guidelines = (
                "\n\n## RESPONSE STYLE\n"
                "Unless the system prompt above says otherwise: "
                "keep spoken responses short, direct, and meaningful — one or two sentences. "
                "No filler, no repetition, no over-explanation.\n\n"
                "## ANSWER HANDLING\n"
                "Unless the system prompt above specifies different behavior:\n"
                "- Clear, relevant answer: acknowledge briefly, then continue to the next topic or question in the same turn.\n"
                "- Off-topic or unclear answer: acknowledge what was said, then redirect back.\n"
                "- Self-correction: accept it naturally and move on.\n"
                "- Wrapping up: brief personal summary, warm sign-off."
            )
            instructions += _default_guidelines

            # Store the FULL instructions (with language directive) so the
            # LLM bridge uses the same prompt for every conversation turn.
            # Previously only the Agent got the enhanced instructions while
            # the bridge received the raw system_prompt — causing the LLM
            # to revert to English after the first greeting.
            self._enhanced_instructions = instructions

            agent = Agent(instructions=instructions)
            await self._agent_session.start(
                room=room,
                agent=agent,
                room_options=RoomOptions(
                    text_output=TextOutputOptions(sync_transcription=False),
                ),
            )

            # Let the LLM generate its own greeting based on the system prompt.
            # The system prompt already enforces language — the LLM will greet
            # in the configured language naturally.
            self._agent_session.generate_reply(
                user_input=f'A new user has just joined. Your name is "{bot_name}". Introduce yourself using that exact name and greet them warmly in character.',
            )

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
            "stt_language": self.snapshot.stt_language,
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
            "tts_language": self.snapshot.tts_language,
            "tts_custom_model": self.snapshot.tts_custom_model,
            "tts_custom_voice_id": self.snapshot.tts_custom_voice_id,
            "tts_custom_endpoint": self.snapshot.tts_custom_endpoint,
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
        import asyncio

        # Use the enhanced instructions (with language directive) if available,
        # falling back to raw system_prompt. This ensures the LLM sees the
        # language instruction on EVERY turn, not just the first greeting.
        effective_prompt = getattr(self, '_enhanced_instructions', None) or self.snapshot.system_prompt

        llm_config = {
            "api_key": self.snapshot.llm_api_key,
            "base_url": self.snapshot.llm_base_url,
            "model": self.snapshot.llm_model,
        }
        conversation_adapter = DefaultConversationAdapter(llm_config)

        policy = ConversationPolicy()
        bot_config = {
            "system_prompt": effective_prompt,
            "llm_model": self.snapshot.llm_model,
            "llm_provider_id": self.snapshot.llm_provider_id,
            "api_key": self.snapshot.llm_api_key,
            "base_url": self.snapshot.llm_base_url,
        }

        def _schedule_session_end():
            """Schedule room disconnect 5 seconds after farewell."""
            async def _delayed_disconnect():
                await asyncio.sleep(5)
                if not self._is_destroyed and self._room:
                    logger.info("[SESSION] Farewell grace period ended — disconnecting room")
                    await self._room.disconnect()
            asyncio.create_task(_delayed_disconnect())

        return WidTTSLLMBridge(
            bot=bot_config,
            policy=policy,
            conversation_adapter=conversation_adapter,
            on_session_end=_schedule_session_end,
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
