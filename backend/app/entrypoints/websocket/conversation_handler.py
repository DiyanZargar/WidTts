import uuid
import json
import re
import time
import asyncio
from typing import Optional, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query

from app.entrypoints.websocket.connection_manager import manager
from app.entrypoints import response_formatter as fmt
from app.shared.config.runtime_limits import get_limits
from app.shared.logging.logger import logger
from app.shared.logging import pipeline_logger as pl
from app.shared.security.token_service import AuthenticationError, AuthorizationError
from app.shared.events.event_bus import EventBus, Event
from app.shared.cancellation.cancellation_token import CancellationTokenSource
from app.shared.resources.session_resource_manager import SessionResourceManager
from app.shared.providers.provider_health_manager import ProviderHealthManager
from app.shared.capabilities.capability_registry import CapabilityRegistry
from app.shared.errors.error_classifier import classify_error

from app.modules.conversation.domain.models.conversation_fsm import ConversationState, TurnStateTransitionError
from app.modules.conversation.domain.models.turn_context import TurnContext
from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface
from app.modules.message.domain.interfaces.message_repository_interface import MessageRepositoryInterface
from app.modules.conversation.domain.interfaces.response_repository_interface import ResponseRepositoryInterface
from app.modules.conversation.domain.interfaces.validation_provider_interface import ValidationProviderInterface
from app.modules.interruption.domain.interfaces.interruption_repository_interface import InterruptionRepositoryInterface
from app.modules.voice.domain.interfaces.stt_provider_interface import STTProviderInterface
from app.modules.voice.domain.interfaces.tts_provider_interface import TTSProviderInterface
from app.modules.session.application.use_cases.create_session import CreateSession
from app.modules.session.application.use_cases.get_session import GetSession
from app.modules.session.application.use_cases.update_pointer import UpdatePointer
from app.modules.session.application.use_cases.pause_session import PauseSession
from app.modules.session.application.use_cases.close_session import CloseSession
from app.modules.message.application.use_cases.add_message import AddMessage
from app.modules.message.application.use_cases.get_messages import GetMessages
from app.modules.conversation.application.use_cases.record_response import RecordResponse
from app.modules.interruption.application.use_cases.classify_interruption import ClassifyInterruption
from app.modules.interruption.application.use_cases.record_interruption import RecordInterruption
from app.modules.voice.application.use_cases.synthesize_speech import SynthesizeSpeech
from app.modules.conversation.application.services.response_coordinator import ResponseCoordinator
from app.modules.conversation.domain.policy.conversation_policy import ConversationPolicy, PolicyAction
from app.modules.conversation.application.services.context_manager import ContextManager
from app.modules.session.application.services.runtime_state_manager import RuntimeStateManager, ConnectionState, PlaybackState, STTState, TTSState
from app.modules.interruption.infrastructure.external.interruption_classifier_adapter import InterruptionClassifierAdapter
from app.entrypoints.websocket.dependencies import (
    get_session_repository, get_message_repository,
    get_response_repository, get_interruption_repository,
    get_validation_adapter, get_interruption_classifier_adapter, get_current_user,
    get_event_bus, get_conversation_policy, get_context_manager, get_runtime_state_manager,
    get_provider_health, get_capability_registry,
    get_bot_repository, build_speech_adapters_from_bot, build_llm_config_from_bot,
)

router = APIRouter()


def chunk_by_sentence(text: str) -> List[str]:
    """Split text at sentence boundaries (.!?) preserving punctuation.
    Matches the official Deepgram TTS text chunking strategy."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s for s in sentences if s]


@router.websocket("/ws/{conversation_type}")
async def conversation_socket(
    ws: WebSocket,
    conversation_type: str,
    session_id: Optional[str] = Query(None),
    token: Optional[str] = Query(None),
    session_repo: SessionRepositoryInterface = Depends(get_session_repository),
    message_repo: MessageRepositoryInterface = Depends(get_message_repository),
    response_repo: ResponseRepositoryInterface = Depends(get_response_repository),
    interruption_repo: InterruptionRepositoryInterface = Depends(get_interruption_repository),
    validation_adapter: ValidationProviderInterface = Depends(get_validation_adapter),
    interruption_classifier: InterruptionClassifierAdapter = Depends(get_interruption_classifier_adapter),
    event_bus: EventBus = Depends(get_event_bus),
    conversation_policy: ConversationPolicy = Depends(get_conversation_policy),
    context_manager: ContextManager = Depends(get_context_manager),
    runtime_state: RuntimeStateManager = Depends(get_runtime_state_manager),
    provider_health: ProviderHealthManager = Depends(get_provider_health),
    capability_registry: CapabilityRegistry = Depends(get_capability_registry),
):
    limits = get_limits()

    try:
        current_user_id = get_current_user(token)
    except AuthenticationError as e:
        await ws.accept()
        await ws.send_json(fmt.error_event(f"Authentication failed: {str(e)}"))
        await ws.close(code=4001)
        return

    # ── Resolve active bot and build providers ──
    bot_repo = get_bot_repository()
    active_bot = await bot_repo.get_active()
    if not active_bot:
        await ws.accept()
        await ws.send_json(fmt.error_event("No active bot configured. Please contact admin."))
        await ws.close(code=4002)
        return

    try:
        stt_adapter, tts_adapter = await build_speech_adapters_from_bot(active_bot)
        llm_config = await build_llm_config_from_bot(active_bot)
    except Exception as e:
        await ws.accept()
        await ws.send_json(fmt.error_event(f"Bot configuration error: {str(e)}"))
        await ws.close(code=4002)
        return

    bot_system_prompt = active_bot.get("system_prompt", "")
    bot_name = active_bot.get("name", "Assistant")

    create_session = CreateSession(session_repo)
    get_session = GetSession(session_repo)
    update_pointer = UpdatePointer(session_repo)
    pause_session = PauseSession(session_repo)
    close_session = CloseSession(session_repo)
    add_message = AddMessage(message_repo)
    get_messages = GetMessages(message_repo)
    record_response = RecordResponse(response_repo)
    classify_interruption = ClassifyInterruption(interruption_classifier)
    record_interruption = RecordInterruption(interruption_repo)
    synthesize_speech = SynthesizeSpeech(tts_adapter)

    # Inject LLM config into validation adapter for bot-driven prompting
    if hasattr(validation_adapter, 'set_llm_config'):
        validation_adapter.set_llm_config(llm_config)
    if hasattr(interruption_classifier, 'set_llm_config'):
        interruption_classifier.set_llm_config(llm_config)

    is_recovery = False
    if session_id:
        existing = await get_session.execute(session_id)
        if existing:
            owner_id = existing.get("user_id", "anonymous")
            if owner_id != current_user_id:
                await ws.accept()
                await ws.send_json(fmt.error_event("Unauthorized session recovery: user does not own this session."))
                await ws.close(code=4003)
                return
            if existing["status"] in ("active", "paused"):
                is_recovery = True
            else:
                session_id = str(uuid.uuid4())
        else:
            session_id = str(uuid.uuid4())
    else:
        session_id = str(uuid.uuid4())

    await manager.connect(session_id, ws)
    pl.websocket_connected(session_id)

    # ── Session-scoped resources ──
    cancel_source = CancellationTokenSource()
    resources = SessionResourceManager(session_id)
    resources.register_websocket(ws)

    rt = runtime_state.create_session(session_id, conversation_type, user_id=current_user_id, is_recovery=is_recovery)

    await manager.send_json(session_id, fmt.event("session_started", {
        "session_id": session_id, "user_id": current_user_id, "is_recovery": is_recovery,
        "bot_name": bot_name,
    }))
    pl.session_start(session_id, conversation_type, is_recovery)
    pl.conversation_start(session_id, conversation_type)

    if not is_recovery:
        await create_session.execute(session_id, conversation_type, user_id=current_user_id, bot_id=active_bot["id"])
        index, retries = 0, 0
    else:
        session_data = await get_session.execute(session_id)
        index = session_data["current_question_index"] if session_data else 0
        retries = session_data["retries"] if session_data else 0
        await update_pointer.execute(session_id, index, "asking", retries)

    try:
        await stt_adapter.connect()
        resources.register_stt_stream(stt_adapter)
        provider_health.record_success("stt")
        runtime_state.set_stt_state(session_id, STTState.LISTENING)
        pl.stt_connected(session_id)
    except Exception as e:
        provider_health.record_failure("stt", str(e))
        pl.error_occurred(session_id, "", "stt", "connect", str(e))

    try:
        await tts_adapter.connect_stream()
        resources.register_tts_stream(tts_adapter)
        provider_health.record_success("tts")
        runtime_state.set_tts_state(session_id, TTSState.SYNTHESIZING)
        pl.tts_connected(session_id)
    except Exception as e:
        provider_health.record_failure("tts", str(e))
        pl.error_occurred(session_id, "", "tts", "connect_stream", str(e))

    current_turn: Optional[TurnContext] = None
    current_tts_text: str = ""

    response_coordinator = ResponseCoordinator(event_bus, synthesize_speech, validation_adapter)
    response_coordinator.set_cancellation_token(cancel_source.token)

    async def _on_tts_chunk(event: Event):
        chunk = event.payload.get("chunk")
        if chunk:
            await manager.send_bytes(session_id, chunk)
            pl.tts_send_to_client(session_id, event.payload.get("turn_id", ""), len(chunk))

    async def _on_tts_audio_meta(event: Event):
        await manager.send_json(session_id, fmt.event("tts_audio_meta", event.payload))

    async def _on_tts_stream_end(event: Event):
        await manager.send_json(session_id, fmt.event("tts_stream_end", event.payload))

    event_bus.subscribe_async("tts_audio_chunk", _on_tts_chunk)
    event_bus.subscribe_async("tts_audio_meta", _on_tts_audio_meta)
    event_bus.subscribe_async("tts_stream_end", _on_tts_stream_end)
    resources.register_event_subscription(lambda: event_bus.unsubscribe("tts_audio_chunk", _on_tts_chunk))
    resources.register_event_subscription(lambda: event_bus.unsubscribe("tts_audio_meta", _on_tts_audio_meta))
    resources.register_event_subscription(lambda: event_bus.unsubscribe("tts_stream_end", _on_tts_stream_end))

    async def speak(text: str) -> None:
        nonlocal current_tts_text
        current_tts_text = text
        turn_id = current_turn.turn_id if current_turn else ""
        pl.tts_synthesize_start(session_id, turn_id, text)
        await add_message.execute(session_id, "system", text)
        context_manager.add_message(session_id, "system", text, turn_id)
        if current_turn and not current_turn.is_destroyed:
            current_turn.fsm.transition_to(ConversationState.TTS_PLAYING, reason="Sending TTS audio to client")
        runtime_state.set_playback_state(session_id, PlaybackState.PLAYING, tts_text=text)
        await manager.send_json(session_id, fmt.event("tts_audio_meta", {"text": text, "is_streaming": True, "chunk_count": 0}))
        total_bytes = 0
        chunk_count = 0
        _t0 = time.monotonic()
        try:
            async for chunk in synthesize_speech.synthesize_stream(text):
                if not chunk:
                    continue
                total_bytes += len(chunk)
                chunk_count += 1
                runtime_state.record_tts_chunk(session_id, len(chunk))
                await manager.send_bytes(session_id, chunk)
                pl.tts_send_to_client(session_id, turn_id, len(chunk))
        except Exception as e:
            provider_health.record_failure("tts", str(e))
            logger.error(f"[TTS STREAM ERROR] session_id={session_id}: {e}")
            audio = await synthesize_speech.execute(text)
            await manager.send_bytes(session_id, audio)
            total_bytes = len(audio)
            chunk_count = 1
        else:
            provider_health.record_success("tts")

        _tts_synth_ms = int((time.monotonic() - _t0) * 1000)
        pl.tts_synthesize_end(session_id, turn_id, _tts_synth_ms, total_bytes)
        logger.info(f"[TTS STREAM END] session_id={session_id} chunks={chunk_count} bytes={total_bytes} duration_ms={_tts_synth_ms}")
        await manager.send_json(session_id, fmt.event("tts_stream_end", {"text": text, "chunks": chunk_count, "bytes": total_bytes}))
        runtime_state.set_playback_state(session_id, PlaybackState.IDLE)
        new_epoch = stt_adapter.advance_epoch()
        runtime_state.advance_epoch(session_id)
        pl.stt_epoch_advance(session_id, turn_id, new_epoch)
        if current_turn and not current_turn.is_destroyed:
            current_turn.listening_epoch = new_epoch
            await stt_adapter.drain_before(new_epoch)
            current_turn.fsm.transition_to(ConversationState.LISTENING, reason="TTS sent, STT listening in parallel")

    # ── Bot-driven conversation: the system prompt IS the conversation logic ──
    # The bot's system prompt tells the LLM what to do, when to advance, etc.
    # We send the user's greeting and let the LLM drive the flow.

    async def handle_user_message(transcript: str) -> None:
        nonlocal current_turn, index, retries, cancel_source

        await manager.send_json(session_id, fmt.event("user_transcript", {"text": transcript}))
        await add_message.execute(session_id, "user", transcript)
        context_manager.add_message(session_id, "user", transcript, current_turn.turn_id if current_turn else None)

        if current_turn and not current_turn.is_destroyed:
            current_turn.fsm.transition_to(ConversationState.VALIDATING, reason="Processing user message")

        # Stream LLM response using bot's system prompt
        turn_id = current_turn.turn_id if current_turn else ""
        try:
            result = await response_coordinator.stream_bot_response(
                transcript=transcript,
                session_id=session_id,
                turn_id=turn_id,
                system_prompt=bot_system_prompt,
                llm_config=llm_config,
                context=context_manager.get_context(session_id),
                turn_context=current_turn,
            )
        except asyncio.CancelledError:
            if current_turn and not current_turn.is_destroyed:
                current_turn.fsm.transition_to(ConversationState.LISTENING, reason="LLM cancelled")
            return

        if result and result.get("text"):
            response_text = result["text"]
            await add_message.execute(session_id, "system", response_text)
            context_manager.add_message(session_id, "system", response_text, turn_id)
            # Note: TTS was already streamed inside stream_bot_response via _tts_flush
            # so we just advance the STT epoch to discard stale transcripts
            new_epoch = stt_adapter.advance_epoch()
            runtime_state.advance_epoch(session_id)
            if current_turn and not current_turn.is_destroyed:
                current_turn.listening_epoch = new_epoch
                await stt_adapter.drain_before(new_epoch)

        if current_turn and not current_turn.is_destroyed:
            if current_turn.fsm.current_state != ConversationState.LISTENING:
                current_turn.fsm.transition_to(ConversationState.LISTENING, reason="LLM response complete")

    try:
        # Send initial greeting based on bot personality
        greeting = f"Hello! I'm {bot_name}."
        if active_bot.get("personality"):
            greeting = active_bot["personality"]
        await speak(greeting)

        # Create initial turn
        if current_turn:
            current_turn.destroy()
        current_turn = TurnContext(
            session_id=session_id, conversation_id=conversation_type,
            question_id="bot_turn", sequence_number=index,
            question_text="", expected_context="",
            retry_counter=retries,
        )
        runtime_state.set_turn(session_id, current_turn.turn_id, index)
        current_turn.fsm.transition_to(ConversationState.LISTENING, reason="Initial — waiting for user")

        while True:
            frame = await ws.receive()
            if frame.get("type") == "websocket.disconnect":
                pl.ws_disconnect(session_id)
                logger.info(f"[WS DISCONNECT] Client disconnected session_id={session_id}")
                break
            if not current_turn or current_turn.is_destroyed:
                continue

            if "text" in frame and frame["text"] is not None:
                try:
                    msg = json.loads(frame["text"])
                    msg_type = msg.get("type")
                    if msg_type == "tts_end":
                        continue
                    elif msg_type == "tts_interrupt":
                        pl.ws_control_message(session_id, "tts_interrupt")
                        cancel_source.cancel("tts_interrupt")
                        cancel_source = CancellationTokenSource()
                        response_coordinator.set_cancellation_token(cancel_source.token)
                        if current_turn and not current_turn.is_destroyed:
                            current_turn.cancel_active_llm()
                            logger.info(f"[TTS INTERRUPT] Cancelled in-flight generation for turn_id={current_turn.turn_id}")
                        continue
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"[WS MSG ERROR] Failed to parse JSON message: {e}")
                continue

            if "bytes" in frame and frame["bytes"] is not None:
                pl.stt_audio_sent(session_id, len(frame["bytes"]))
                await stt_adapter.send_audio(frame["bytes"])

                transcript_parts = []
                while True:
                    raw = await stt_adapter.receive_any()
                    if not raw:
                        break
                    item_epoch = raw.pop("_epoch", 0)
                    if current_turn and item_epoch < current_turn.listening_epoch:
                        pl.stt_stale_discarded(session_id, current_turn.turn_id, item_epoch, current_turn.listening_epoch)
                        continue
                    text, is_final = stt_adapter.parse_stt_message(raw)
                    if text and not is_final:
                        if current_turn and not current_turn.is_destroyed:
                            pl.stt_partial_transcript(session_id, current_turn.turn_id, item_epoch, text)
                            current_turn.add_partial_transcript(text)
                            await manager.send_json(session_id, fmt.event("user_partial_transcript", {"text": text}))
                    elif is_final and text:
                        if current_turn and not current_turn.is_destroyed:
                            pl.stt_final_transcript(session_id, current_turn.turn_id, item_epoch, text)
                            current_turn.set_final_transcript(text)
                            transcript_parts.append(text)
                transcript = " ".join(transcript_parts) if transcript_parts else None
                if transcript:
                    current_turn.set_final_transcript(transcript)
                    pl.transcript_assigned(session_id, current_turn.turn_id, current_turn.transcript_id or "", transcript)
                if not transcript:
                    continue
            else:
                continue

            # Process the transcript through bot-driven conversation
            await handle_user_message(transcript)

    except (WebSocketDisconnect, RuntimeError) as e:
        err = classify_error("connection_lost", str(e))
        logger.warning(f"[WS ERROR/DISCONNECT] {err.category.value} session_id={session_id}: {e}")
        await pause_session.execute(session_id)
    finally:
        cancel_source.cancel("session_end")
        pl.session_end(session_id, "handler_exit")
        pl.conversation_end(session_id, "handler_exit")
        if current_turn:
            pl.turn_destroy(current_turn.turn_id, session_id, "handler_exit")
            current_turn.destroy()
        await stt_adapter.close()
        await tts_adapter.close()
        runtime_state.destroy_session(session_id)
        await resources.release_all()
        if manager.active.get(session_id) is ws:
            manager.disconnect(session_id)
