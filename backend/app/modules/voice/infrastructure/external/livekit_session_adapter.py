"""LiveKit Session Adapter. Manages the full lifecycle of an agent session
in a LiveKit room — building STT/TTS plugins, the LLM bridge, and the
AgentSession, then tearing everything down on destroy."""
import logging
import time
from typing import Optional, Any, cast
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
    llm_provider_type: str = ""
    encrypted_stt_credentials: dict = field(default_factory=dict)
    stt_key_version: int = 0
    encrypted_tts_credentials: dict = field(default_factory=dict)
    tts_key_version: int = 0


# Global cached VAD instance to eliminate 300-500ms model loading latency on every session start
_CACHED_VAD = None


def _get_vad_plugin():
    global _CACHED_VAD
    if _CACHED_VAD is None:
        from livekit.plugins import silero
        from app.shared.config.knobs import knobs
        _CACHED_VAD = silero.VAD.load(**knobs.to_silero_vad_kwargs())
    return _CACHED_VAD


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
            from livekit.agents.voice.room_io import RoomOptions, TextOutputOptions, AudioOutputOptions
            from app.shared.config.knobs import knobs

            self._stt_plugin = await self._build_stt()
            self._tts_plugin = await self._build_tts()
            self._llm_bridge = self._build_llm_bridge()
            self._vad_plugin = _get_vad_plugin()

            timeout_sec = knobs.runtime.user_away_timeout

            self._agent_session = AgentSession(
                vad=self._vad_plugin,
                stt=self._stt_plugin,
                llm=self._llm_bridge,
                tts=self._tts_plugin,
                user_away_timeout=timeout_sec,
                turn_handling=cast(Any, knobs.to_turn_handling_dict()),
                aec_warmup_duration=knobs.runtime.aec_warmup_duration,
                transcription_timeout=knobs.runtime.transcription_timeout,
                session_close_transcript_timeout=knobs.runtime.session_close_transcript_timeout,
                min_consecutive_speech_delay=knobs.runtime.min_consecutive_speech_delay,
                max_tool_steps=knobs.runtime.max_tool_steps,
                use_tts_aligned_transcript=knobs.runtime.use_tts_aligned_transcript,
                tts_text_transforms=cast(Any, knobs.runtime.tts_text_transforms),
                expressive=knobs.runtime.expressive,
                ivr_detection=knobs.runtime.ivr_detection,
            )

            # Handle inactivity timeout (user away for timeout_sec)
            @self._agent_session.on("user_state_changed")
            def _on_user_state_changed(ev):
                if getattr(ev, "new_state", None) == "away":
                    logger.info("[SESSION] Inactivity timeout (%ss) reached for session=%s", timeout_sec, self.snapshot.session_id)
                    import asyncio

                    async def _farewell_then_disconnect():
                        # 1. Play a farewell message via TTS (prompt-independent)
                        try:
                            if self._agent_session and not self._is_destroyed:
                                self._agent_session.say(
                                    knobs.llm.default_farewell_speech,
                                    allow_interruptions=False,
                                )
                                # Give TTS time to synthesize + play the farewell
                                await asyncio.sleep(knobs.runtime.farewell_drain_delay)
                        except Exception as e:
                            logger.warning("[SESSION] Farewell TTS failed: %s", e)

                        # 2. Notify frontend before disconnecting
                        try:
                            target_room = self._room or (self._agent_session.room if self._agent_session else None)
                            if target_room and target_room.local_participant:
                                import json
                                payload = json.dumps({
                                    "event": "session_end",
                                    "payload": {"reason": "inactivity_timeout"},
                                }).encode("utf-8")
                                await target_room.local_participant.publish_data(payload)
                                logger.info("[SESSION] Published session_end event to room for session=%s", self.snapshot.session_id)
                                await asyncio.sleep(knobs.runtime.farewell_publish_delay)  # brief pause for data delivery
                        except Exception as e:
                            logger.warning("[SESSION] Failed to publish session_end: %s", e)

                        # 3. Tear down session
                        await self.destroy()

                    asyncio.create_task(_farewell_then_disconnect())

            # Fast barge-in for short concrete words ("wait", "stop", "no no", etc.)
            @self._agent_session.on("user_input_transcribed")
            def _on_user_input_transcribed(ev):
                transcript = (getattr(ev, "transcript", None) or "").strip().lower()
                if not transcript:
                    return

                # If agent is currently speaking, check if the utterance contains urgent interruption words
                is_speaking = getattr(self._agent_session, "agent_state", None) == "speaking" or bool(getattr(self._agent_session, "current_speech", None))
                if is_speaking:
                    urgent_words = knobs.policy.urgent_interruption_words
                    clean_text = "".join(c for c in transcript if c.isalnum() or c.isspace()).strip()
                    words = clean_text.split()
                    if clean_text in urgent_words or any(w in urgent_words for w in words):
                        logger.info("[SESSION] Urgent interruption keyword detected: '%s' — interrupting agent", transcript)
                        try:
                            self._agent_session.interrupt()
                        except Exception as e:
                            logger.warning("[SESSION] Urgent interruption failed: %s", e)

            # Build system instructions with bot identity and language (strictly from snapshot)
            bot_name = (self.snapshot.bot_name or "").strip()
            bot_desc = (self.snapshot.bot_description or "").strip()
            lang = self.snapshot.tts_primary_language or "en"
            farewell_marker = knobs.llm.farewell_marker

            if bot_name:
                identity = f"Your name is \"{bot_name}\". You MUST use this name when introducing yourself — never invent, guess, or substitute a different name."
            else:
                identity = ""

            if bot_desc:
                identity = f"{identity} {bot_desc}".strip()

            if lang and lang != "en":
                identity += (
                    f" You MUST ALWAYS respond in language '{lang}' and no other language."
                    f" This is non-negotiable — every response, every word, must be in '{lang}'."
                    f" When you need to end the conversation or say goodbye, append the marker {farewell_marker} at the very end of your response."
                )
            else:
                identity += f" When you need to end the conversation or say goodbye, append the marker {farewell_marker} at the very end of your response."
            
            instructions = f"{identity}\n\n{self.snapshot.system_prompt}" if self.snapshot.system_prompt else identity

            # Voice conversational guidelines
            _voice_guidelines = (
                "\n\n## SPOKEN VOICE RULES\n"
                "- This is a real-time spoken audio conversation. Speak naturally, clearly, and concisely.\n"
                "- Keep each spoken turn to 1-2 sentences unless specifically asked for more.\n"
                "- Never use markdown formatting (no asterisks, no bullets, no headers, no emojis).\n"
                "- Directly answer or follow the active conversational step without filler."
            )
            instructions += _voice_guidelines

            self._enhanced_instructions = instructions

            agent = Agent(instructions=instructions)
            await self._agent_session.start(
                room=room,
                agent=agent,
                room_options=RoomOptions(
                    text_output=TextOutputOptions(
                        sync_transcription=knobs.room.sync_transcription,
                        transcription_speed_factor=knobs.room.transcription_speed_factor,
                        json_format=knobs.room.json_format,
                    ),
                    audio_output=AudioOutputOptions(
                        sample_rate=knobs.room.audio_output_sample_rate,
                        num_channels=knobs.room.audio_output_num_channels,
                        track_name=knobs.room.audio_output_track_name,
                    ),
                    close_on_disconnect=knobs.room.close_on_disconnect,
                    delete_room_on_close=knobs.room.delete_room_on_close,
                ),
            )

            # Greeting — wait for audio pipeline to stabilize before
            # sending the first TTS utterance. Without this delay the
            # WebRTC audio track isn't fully negotiated and the first
            # word gets clipped/broken.
            import asyncio as _aio
            await _aio.sleep(knobs.runtime.greeting_stabilization_delay)

            custom_greeting = (self.snapshot.greeting or "").strip()
            if not custom_greeting:
                custom_greeting = f"Hello! I am {bot_name}. How can I help you today?" if bot_name else "Hello! How can I help you today?"
            logger.info("[SESSION] Playing instant direct greeting: %s", custom_greeting[:60])
            self._agent_session.say(custom_greeting)

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
        from app.modules.voice.infrastructure.external.llm_bridge import (
            CustomLLMBridge,
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
            "provider_type": self.snapshot.llm_provider_type,
        }
        conversation_adapter = DefaultConversationAdapter(llm_config)

        policy = ConversationPolicy()
        bot_config = {
            "system_prompt": effective_prompt,
            "llm_model": self.snapshot.llm_model,
            "llm_provider_id": self.snapshot.llm_provider_id,
            "llm_provider_type": self.snapshot.llm_provider_type,
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

        return CustomLLMBridge(
            bot=bot_config,
            policy=policy,
            conversation_adapter=conversation_adapter,
            session_id=self.snapshot.session_id,
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

        # Mark session as completed in database
        try:
            from app.modules.session.infrastructure.persistence.session_repository import (
                SessionRepository,
            )
            await SessionRepository().close(self.snapshot.session_id, status="completed")
            logger.info("[SESSION] Marked session %s as completed in database", self.snapshot.session_id)
        except Exception as e:
            logger.warning("[SESSION] Failed to mark session %s as completed in DB: %s", self.snapshot.session_id, e)

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

        if self._room:
            try:
                await self._room.disconnect()
            except Exception as e:
                logger.warning("[SESSION] Room disconnect error: %s", e)
            self._room = None
        self._stt_plugin = None
        self._tts_plugin = None
        self._vad_plugin = None
        self._llm_bridge = None
        logger.info("[SESSION] Session destroyed: %s", self.snapshot.session_id)
        pl.session_end(session_id=self.snapshot.session_id, reason="session_destroyed")

    @property
    def is_destroyed(self) -> bool:
        return self._is_destroyed
