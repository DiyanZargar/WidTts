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
    _farewell_task: Any = field(default=None, repr=False)
    _watchdog_task: Any = field(default=None, repr=False)
    _last_voice_activity: float = field(default_factory=time.monotonic, repr=False)
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

            # Set user_away_timeout=None so LiveKit's internal opaque timer is disabled.
            # Inactivity is governed by our transparent Silero VAD / STT / TTS watchdog.
            self._agent_session = AgentSession(
                vad=self._vad_plugin,
                stt=self._stt_plugin,
                llm=self._llm_bridge,
                tts=self._tts_plugin,
                user_away_timeout=None,
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

            def _mark_voice_activity():
                self._last_voice_activity = time.monotonic()
                if self._farewell_task and not self._farewell_task.done():
                    logger.info("[SESSION] Voice activity detected — cancelling farewell disconnect for session=%s", self.snapshot.session_id)
                    self._farewell_task.cancel()
                    self._farewell_task = None

            # Silero VAD state events: refresh on speech detection
            @self._agent_session.on("user_state_changed")
            def _on_user_state_changed(ev):
                new_state = getattr(ev, "new_state", None)
                if new_state in ("speaking", "listening"):
                    _mark_voice_activity()

            # STT input events: refresh on transcribed user speech
            @self._agent_session.on("user_input_transcribed")
            def _on_user_input_transcribed(ev):
                _mark_voice_activity()
                transcript = (getattr(ev, "transcript", None) or "").strip().lower()
                if not transcript:
                    return

                # If agent is currently speaking, check for urgent interruption words
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

            # Agent state events: refresh when agent is speaking or thinking
            @self._agent_session.on("agent_state_changed")
            def _on_agent_state_changed(ev):
                new_state = getattr(ev, "new_state", None)
                if new_state in ("speaking", "thinking"):
                    _mark_voice_activity()

            # Inactivity watchdog: monitors mutual silence across Silero VAD, STT, and TTS
            if timeout_sec and timeout_sec > 0:
                import asyncio

                async def _inactivity_watchdog():
                    try:
                        while not self._is_destroyed:
                            await asyncio.sleep(1.0)
                            if self._is_destroyed:
                                break

                            user_state = getattr(self._agent_session, "user_state", None)
                            agent_state = getattr(self._agent_session, "agent_state", None)
                            has_speech = bool(getattr(self._agent_session, "current_speech", None))

                            if user_state == "speaking" or agent_state in ("speaking", "thinking") or has_speech:
                                self._last_voice_activity = time.monotonic()
                                continue

                            silence_sec = time.monotonic() - self._last_voice_activity
                            if silence_sec >= timeout_sec:
                                logger.info(
                                    "[SESSION] Continuous silence for %.1fs (limit %ss) — triggering farewell for session=%s",
                                    silence_sec, timeout_sec, self.snapshot.session_id,
                                )

                                async def _farewell_then_disconnect():
                                    try:
                                        try:
                                            if self._agent_session and not self._is_destroyed:
                                                self._agent_session.say(
                                                    knobs.llm.default_farewell_speech,
                                                    allow_interruptions=True,
                                                )
                                                await asyncio.sleep(knobs.runtime.farewell_drain_delay)
                                        except asyncio.CancelledError:
                                            raise
                                        except Exception as e:
                                            logger.warning("[SESSION] Farewell TTS failed: %s", e)

                                        try:
                                            target_room = self._room or (self._agent_session.room if self._agent_session else None)
                                            if target_room and target_room.local_participant and not self._is_destroyed:
                                                import json
                                                payload = json.dumps({
                                                    "event": "session_end",
                                                    "payload": {"reason": "inactivity_timeout"},
                                                }).encode("utf-8")
                                                await target_room.local_participant.publish_data(payload)
                                                logger.info("[SESSION] Published session_end event for session=%s", self.snapshot.session_id)
                                                await asyncio.sleep(knobs.runtime.farewell_publish_delay)
                                        except asyncio.CancelledError:
                                            raise
                                        except Exception as e:
                                            logger.warning("[SESSION] Failed to publish session_end: %s", e)

                                        if not self._is_destroyed:
                                            await self.destroy()
                                    except asyncio.CancelledError:
                                        logger.info("[SESSION] Farewell disconnect cancelled — session remains active")

                                if self._farewell_task and not self._farewell_task.done():
                                    self._farewell_task.cancel()
                                self._farewell_task = asyncio.create_task(_farewell_then_disconnect())
                                break
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        logger.warning("[SESSION] Inactivity watchdog error: %s", e)

                self._watchdog_task = asyncio.create_task(_inactivity_watchdog())

            # Build system instructions with bot identity and language (strictly from snapshot)
            bot_name = (self.snapshot.bot_name or "").strip()
            bot_desc = (self.snapshot.bot_description or "").strip()
            lang = self.snapshot.tts_primary_language or "en"

            identity_parts = []
            if bot_name:
                identity_parts.append(f"Your name is \"{bot_name}\". You MUST use this name when introducing yourself — never invent, guess, or substitute a different name.")
            if bot_desc:
                identity_parts.append(bot_desc)
            if lang and lang != "en":
                identity_parts.append(f"You MUST ALWAYS respond in language '{lang}' and no other language. This is non-negotiable — every response, every word, must be in '{lang}'.")

            identity = " ".join(identity_parts).strip()
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
            """Schedule room disconnect 5 seconds after explicit farewell command."""
            async def _delayed_disconnect():
                try:
                    await asyncio.sleep(5)
                    if not self._is_destroyed and self._room:
                        logger.info("[SESSION] Farewell grace period ended — disconnecting room")
                        await self._room.disconnect()
                except asyncio.CancelledError:
                    logger.info("[SESSION] Explicit farewell disconnect cancelled by new user activity")
            if self._farewell_task and not self._farewell_task.done():
                self._farewell_task.cancel()
            self._farewell_task = asyncio.create_task(_delayed_disconnect())

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

        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
            self._watchdog_task = None
        if self._farewell_task and not self._farewell_task.done():
            self._farewell_task.cancel()
            self._farewell_task = None

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
