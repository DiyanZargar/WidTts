import uuid
import json
import re
import time
import asyncio
from typing import Optional, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query

from app.entrypoints.websocket.connection_manager import manager
from app.entrypoints import response_formatter as fmt
from app.shared.config.settings import settings
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
from app.modules.conversation.domain.interfaces.conversation_repository_interface import ConversationRepositoryInterface
from app.modules.conversation.domain.interfaces.response_repository_interface import ResponseRepositoryInterface
from app.modules.conversation.domain.interfaces.validation_provider_interface import ValidationProviderInterface
from app.modules.interruption.domain.interfaces.interruption_repository_interface import InterruptionRepositoryInterface
from app.modules.voice.domain.interfaces.stt_provider_interface import STTProviderInterface
from app.modules.voice.infrastructure.external.deepgram_stt_adapter import DeepgramSTTAdapter
from app.modules.voice.domain.interfaces.tts_provider_interface import TTSProviderInterface
from app.modules.session.application.use_cases.create_session import CreateSession
from app.modules.session.application.use_cases.get_session import GetSession
from app.modules.session.application.use_cases.update_pointer import UpdatePointer
from app.modules.session.application.use_cases.pause_session import PauseSession
from app.modules.session.application.use_cases.close_session import CloseSession
from app.modules.message.application.use_cases.add_message import AddMessage
from app.modules.message.application.use_cases.get_messages import GetMessages
from app.modules.conversation.application.services.conversation_engine import ConversationEngine
from app.modules.conversation.application.use_cases.validate_response import ValidateResponse
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
    get_session_repository, get_message_repository, get_conversation_repository,
    get_response_repository, get_interruption_repository, get_stt_adapter, get_tts_adapter,
    get_validation_adapter, get_interruption_classifier_adapter, get_current_user,
    get_event_bus, get_conversation_policy, get_context_manager, get_runtime_state_manager,
    get_provider_health, get_capability_registry,
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
    conversation_repo: ConversationRepositoryInterface = Depends(get_conversation_repository),
    response_repo: ResponseRepositoryInterface = Depends(get_response_repository),
    interruption_repo: InterruptionRepositoryInterface = Depends(get_interruption_repository),
    stt_adapter: STTProviderInterface = Depends(get_stt_adapter),
    tts_adapter: TTSProviderInterface = Depends(get_tts_adapter),
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

    create_session = CreateSession(session_repo)
    get_session = GetSession(session_repo)
    update_pointer = UpdatePointer(session_repo)
    pause_session = PauseSession(session_repo)
    close_session = CloseSession(session_repo)
    add_message = AddMessage(message_repo)
    get_messages = GetMessages(message_repo)
    conversation_engine = ConversationEngine(conversation_repo)
    validate_response = ValidateResponse(validation_adapter)
    record_response = RecordResponse(response_repo)
    classify_interruption = ClassifyInterruption(interruption_classifier)
    record_interruption = RecordInterruption(interruption_repo)
    synthesize_speech = SynthesizeSpeech(tts_adapter)

    is_recovery = False
    if session_id:
        existing = get_session.execute(session_id)
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
        "session_id": session_id, "user_id": current_user_id, "is_recovery": is_recovery
    }))
    pl.session_start(session_id, conversation_type, is_recovery)
    pl.conversation_start(session_id, conversation_type)

    if not is_recovery:
        create_session.execute(session_id, conversation_type, user_id=current_user_id)
        index, retries = 0, 0
    else:
        session_data = get_session.execute(session_id)
        index = session_data["current_question_index"] if session_data else 0
        retries = session_data["retries"] if session_data else 0
        update_pointer.execute(session_id, index, "asking", retries)

    try:
        await stt_adapter.connect()
        resources.register_stt_stream(stt_adapter)
        provider_health.record_success("deepgram_stt")
        runtime_state.set_stt_state(session_id, STTState.LISTENING)
        pl.stt_connected(session_id)
    except Exception as e:
        provider_health.record_failure("deepgram_stt", str(e))
        pl.error_occurred(session_id, "", "stt", "connect", str(e))

    try:
        await tts_adapter.connect_stream()
        resources.register_tts_stream(tts_adapter)
        provider_health.record_success("deepgram_tts")
        runtime_state.set_tts_state(session_id, TTSState.SYNTHESIZING)
        pl.tts_connected(session_id)
    except Exception as e:
        provider_health.record_failure("deepgram_tts", str(e))
        pl.error_occurred(session_id, "", "tts", "connect_stream", str(e))

    current_turn: Optional[TurnContext] = None
    current_tts_text: str = ""

    response_coordinator = ResponseCoordinator(event_bus, synthesize_speech, validate_response.execute_stream)
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

    def start_new_turn() -> Optional[TurnContext]:
        nonlocal current_turn, index, retries
        if current_turn:
            current_turn.destroy()
        item = conversation_engine.get_current(conversation_type, index)
        if item is None:
            return None
        current_turn = TurnContext(
            session_id=session_id, conversation_id=conversation_type,
            question_id=item["sequence"], sequence_number=index,
            question_text=item["text"], expected_context=item["expected_context"],
            retry_counter=retries,
        )
        runtime_state.set_turn(session_id, current_turn.turn_id, index)
        pl.turn_create(current_turn.turn_id, session_id, current_turn.question_id, index, item["text"])
        return current_turn

    async def speak(text: str) -> None:
        nonlocal current_tts_text
        current_tts_text = text
        turn_id = current_turn.turn_id if current_turn else ""
        pl.tts_synthesize_start(session_id, turn_id, text)
        add_message.execute(session_id, "system", text)
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
            provider_health.record_failure("deepgram_tts", str(e))
            logger.error(f"[TTS STREAM ERROR] session_id={session_id}: {e}")
            audio = await synthesize_speech.execute(text)
            await manager.send_bytes(session_id, audio)
            total_bytes = len(audio)
            chunk_count = 1
        else:
            provider_health.record_success("deepgram_tts")

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

    async def ask_current():
        nonlocal current_turn, index
        turn = start_new_turn()
        if turn is None:
            close_session.execute(session_id, "completed")
            await manager.send_json(session_id, fmt.completed_event())
            await ws.close()
            return False
        turn.fsm.transition_to(ConversationState.ASKING, reason="Presenting question")
        item = conversation_engine.get_current(conversation_type, index)
        if item is None:
            return False
        logger.info(f"[QUESTION ASK] Presenting question sequence={index} question_id={item['sequence']} | text='{item['text']}'")
        pl.question_ask(session_id, turn.turn_id, item["sequence"], index, item["text"])
        await manager.send_json(session_id, fmt.question_event(item))
        turn.fsm.transition_to(ConversationState.WAITING_FOR_TTS, reason="Synthesizing question audio")
        await speak(item["text"])
        return True

    async def _tts_stream_text(text: str) -> None:
        try:
            sentences = chunk_by_sentence(text)
            for sentence in sentences:
                async for chunk in synthesize_speech.synthesize_stream(sentence):
                    if chunk:
                        await manager.send_bytes(session_id, chunk)
                        pl.tts_send_to_client(session_id, current_turn.turn_id if current_turn else "", len(chunk))
        except Exception as e:
            logger.error(f"[TTS STREAM ERROR] session_id={session_id}: {e}")
            audio = await synthesize_speech.execute(text)
            await manager.send_bytes(session_id, audio)

    async def _handle_streaming_answer(item, transcript, bound_turn_id, bound_question_id):
        nonlocal current_turn, cancel_source
        if not current_turn or current_turn.is_destroyed:
            logger.warning("[STREAMING ANSWER] No active turn — discarding.")
            return None
        llm_task = asyncio.create_task(
            response_coordinator.stream_response(
                item=item, transcript=transcript, session_id=session_id,
                turn_id=bound_turn_id, question_id=bound_question_id, turn_context=current_turn,
            )
        )
        resources.track_task(llm_task)
        current_turn.active_llm_task = llm_task
        current_turn.register_task(llm_task)

        # ── Background drain: forward mic audio to STT while LLM processes ──
        async def _drain_mic():
            """Keep STT pipeline warm during LLM processing."""
            while not llm_task.done():
                try:
                    frame = await asyncio.wait_for(ws.receive(), timeout=0.2)
                except (asyncio.TimeoutError, Exception):
                    continue
                if "bytes" in frame:
                    try:
                        await stt_adapter.send_audio(frame["bytes"])
                        # Read and discard STT results to prevent queue buildup
                        while True:
                            raw = await stt_adapter.receive_any()
                            if not raw:
                                break
                    except Exception:
                        pass
                elif "text" in frame:
                    try:
                        msg = json.loads(frame["text"])
                        if msg.get("type") == "tts_interrupt":
                            pl.ws_control_message(session_id, "tts_interrupt")
                            cancel_source.cancel("tts_interrupt")
                            cancel_source = CancellationTokenSource()
                            response_coordinator.set_cancellation_token(cancel_source.token)
                            if current_turn and not current_turn.is_destroyed:
                                current_turn.cancel_active_llm()
                            return
                    except Exception:
                        pass

        drain_task = asyncio.create_task(_drain_mic())
        try:
            _llm_t0 = time.monotonic()
            result = await llm_task
            provider_health.record_success("litellm", time.monotonic() - _llm_t0)
        except asyncio.CancelledError:
            provider_health.record_failure("litellm", "cancelled")
            pl.llm_cancelled(session_id, bound_turn_id, "task_cancelled")
            logger.info(f"[STREAMING LLM CANCELLED] turn_id={bound_turn_id}")
            raise
        except Exception as e:
            provider_health.record_failure("litellm", str(e))
            raise
        finally:
            drain_task.cancel()
            try:
                await drain_task
            except (asyncio.CancelledError, Exception):
                pass
        if not current_turn or current_turn.is_destroyed or not current_turn.is_event_valid(
            turn_id=bound_turn_id, question_id=bound_question_id, session_id=session_id
        ):
            logger.warning(f"[TURN DISCARD] Discarding late streaming result for bound_turn_id={bound_turn_id}")
            return None
        current_turn.active_llm_task = None
        current_turn.mark_transcript_consumed()
        return {
            "understood_intent": result.metadata.get("understood_intent", ""),
            "answered": result.metadata.get("answered", result.should_advance),
            "classification": result.classification,
            "relevance": result.metadata.get("relevance", 0.0),
            "completeness": result.metadata.get("completeness", 0.0),
            "missing_information": result.metadata.get("missing_information", []),
            "should_repeat_question": result.metadata.get("should_repeat_question", not result.should_advance),
            "should_follow_up": result.metadata.get("should_follow_up", False),
            "follow_up_question": result.metadata.get("follow_up_question"),
            "should_advance": result.should_advance,
            "reason": result.reason,
            "reasoning": result.metadata.get("reasoning", ""),
            "valid": result.metadata.get("valid", result.should_advance),
            "advance": result.should_advance,
        }

    try:
        if is_recovery:
            past_messages = get_messages.execute(session_id)
            await manager.send_json(session_id, fmt.event("transcript_recovery", {"messages": past_messages}))
            await ask_current()
        else:
            await speak(conversation_engine.get_intro_line(conversation_type))
            if not await ask_current():
                return

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
                    text, is_final = DeepgramSTTAdapter.parse_stt_message(raw)
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

            if current_turn.fsm.current_state not in (ConversationState.LISTENING, ConversationState.TRANSCRIBING, ConversationState.TTS_PLAYING):
                pl.fsm_guard_reject(session_id, current_turn.turn_id, current_turn.fsm.current_state.value)
                continue
            was_tts_playing = current_turn.fsm.current_state == ConversationState.TTS_PLAYING
            if current_turn.fsm.current_state in (ConversationState.LISTENING, ConversationState.TTS_PLAYING):
                current_turn.fsm.transition_to(ConversationState.TRANSCRIBING, reason="Final STT received")
            item = conversation_engine.get_current(conversation_type, index)
            if was_tts_playing:
                pl.interrupt_classify_start(session_id, current_turn.turn_id, transcript, was_tts_playing)
                _classify_t0 = time.monotonic()
                classification = await classify_interruption.execute(
                    transcript=transcript,
                    current_question=item["text"] if item else "",
                    tts_text=current_tts_text,
                    expected_context=item["expected_context"] if item else "",
                    previous_answer=current_turn.final_transcript if current_turn else None,
                    is_tts_playing=was_tts_playing,
                )
            else:
                classification = {"interrupt": False, "type": "ANSWER", "confidence": 1.0}
            interrupt_type = classification.get("type", "NONE")
            interrupt_confidence = classification.get("confidence", 0.0)
            if was_tts_playing:
                _classify_ms = int((time.monotonic() - _classify_t0) * 1000)
                pl.interrupt_classify_end(session_id, current_turn.turn_id, interrupt_type, interrupt_confidence, _classify_ms)
            logger.info(f"[INTERRUPT RESULT] type={interrupt_type} confidence={interrupt_confidence:.2f} transcript='{transcript[:60]}' turn_id={current_turn.turn_id}")

            policy_result = conversation_policy.resolve_action(interrupt_type, transcript, retries)
            action = policy_result["action"]

            if action == PolicyAction.STOP:
                pl.interrupt_routed(session_id, current_turn.turn_id, "STOP", "wait_for_user")
                record_interruption.execute(session_id, "stop", transcript)
                if current_turn:
                    current_turn.fsm.transition_to(ConversationState.LISTENING, reason="User requested stop — waiting")
                continue

            if action == PolicyAction.END_CONVERSATION:
                pl.interrupt_routed(session_id, current_turn.turn_id, "END_CONVERSATION", "reset_conversation")
                record_interruption.execute(session_id, "end_conversation", transcript)
                close_session.execute(session_id, "cancelled")
                await manager.send_json(session_id, fmt.event("session_reset"))
                if current_turn:
                    current_turn.destroy()
                    current_turn = None
                index, retries = 0, 0
                context_manager.clear(session_id)
                cancel_source.cancel("session_reset")
                cancel_source = CancellationTokenSource()
                response_coordinator.set_cancellation_token(cancel_source.token)
                runtime_state.destroy_session(session_id)
                runtime_state.create_session(session_id, conversation_type, user_id=current_user_id)
                create_session.execute(session_id, conversation_type, user_id=current_user_id)
                await speak(conversation_engine.get_intro_line(conversation_type))
                if not await ask_current():
                    break
                continue

            if action == PolicyAction.REPEAT:
                pl.interrupt_routed(session_id, current_turn.turn_id, "REPEAT", "replay_question")
                record_interruption.execute(session_id, "repeat", transcript)
                await ask_current()
                continue

            if action == PolicyAction.CORRECTION:
                pl.interrupt_routed(session_id, current_turn.turn_id, "CORRECTION", "replace_answer")
                record_interruption.execute(session_id, "correction", transcript)
                if current_turn:
                    old_text = current_turn.final_transcript or ""
                    current_turn.apply_correction(transcript)
                    pl.correction_applied(session_id, current_turn.turn_id, old_text, transcript, len(current_turn.correction_stack))
                await manager.send_json(session_id, fmt.event("user_transcript", {"text": transcript, "is_correction": True}))
                add_message.execute(session_id, "user", transcript)
                context_manager.add_message(session_id, "user", transcript, current_turn.turn_id if current_turn else None)
                if current_turn and not current_turn.is_destroyed:
                    current_turn.fsm.transition_to(ConversationState.VALIDATING, reason="Validating corrected answer")
                    bound_turn_id = current_turn.turn_id
                    bound_question_id = item["sequence"] if item else ""
                    try:
                        result = await _handle_streaming_answer(item, transcript, bound_turn_id, bound_question_id)
                    except asyncio.CancelledError:
                        pl.llm_cancelled(session_id, bound_turn_id, "correction_cancelled")
                        if current_turn and not current_turn.is_destroyed:
                            current_turn.fsm.transition_to(ConversationState.LISTENING, reason="Correction streaming cancelled")
                        continue
                    if result is None:
                        continue
                    should_advance = bool(result.get("should_advance", False))
                    spoken_reason = result.get("reason", "Could you say that again?")
                    record_response.execute(item["sequence"], session_id, transcript, "valid" if should_advance else "invalid")
                    await manager.send_json(session_id, fmt.validation_event(should_advance, spoken_reason))
                    if should_advance:
                        current_turn.fsm.transition_to(ConversationState.ADVANCE, reason="Corrected answer validated")
                        index += 1
                        retries = 0
                        update_pointer.execute(session_id, index, "asking", retries)
                        current_turn.fsm.transition_to(ConversationState.NEXT_TURN, reason="Advancing pointer")
                        if not await ask_current():
                            break
                    else:
                        current_turn.fsm.transition_to(ConversationState.RETRY, reason="Corrected answer needs follow-up")
                        retries += 1
                        update_pointer.execute(session_id, index, "repeating", retries)
                        # The LLM's streaming response already spoke the follow-up/clarification.
                        # Just drain stale STT and wait for the user's next answer.
                        if current_turn and not current_turn.is_destroyed:
                            new_epoch = stt_adapter.advance_epoch()
                            runtime_state.advance_epoch(session_id)
                            current_turn.listening_epoch = new_epoch
                            await stt_adapter.drain_before(new_epoch)
                            pl.stt_epoch_advance(session_id, bound_turn_id, new_epoch)
                            if current_turn.fsm.current_state != ConversationState.LISTENING:
                                current_turn.fsm.transition_to(ConversationState.LISTENING, reason="LLM follow-up spoken — listening for answer")
                continue

            if action == PolicyAction.ANSWER or not classification.get("interrupt", False):
                await manager.send_json(session_id, fmt.event("user_transcript", {"text": transcript}))
                add_message.execute(session_id, "user", transcript)
                context_manager.add_message(session_id, "user", transcript, current_turn.turn_id if current_turn else None)
                if not current_turn or current_turn.is_destroyed:
                    continue
                current_turn.fsm.transition_to(ConversationState.VALIDATING, reason="Executing LLM evaluation")
                bound_turn_id = current_turn.turn_id
                bound_question_id = item["sequence"] if item else ""
                _val_t0 = time.monotonic()
                try:
                    result = await _handle_streaming_answer(item, transcript, bound_turn_id, bound_question_id)
                except asyncio.CancelledError:
                    pl.llm_cancelled(session_id, bound_turn_id, "interrupted")
                    if current_turn and not current_turn.is_destroyed:
                        current_turn.fsm.transition_to(ConversationState.LISTENING, reason="Streaming cancelled — waiting for new input")
                    continue
                if result is None:
                    continue
                should_advance = bool(result.get("should_advance", False))
                spoken_reason = result.get("reason", "Could you say that again?")
                _val_ms = int((time.monotonic() - _val_t0) * 1000)
                pl.validation_end(session_id, bound_turn_id, should_advance, _val_ms, spoken_reason)
                record_response.execute(item["sequence"], session_id, transcript, "valid" if should_advance else "invalid")
                await manager.send_json(session_id, fmt.validation_event(should_advance, spoken_reason))
                if should_advance:
                    pl.turn_advance(session_id, bound_turn_id, index, index + 1)
                    current_turn.fsm.transition_to(ConversationState.ADVANCE, reason="Response validated")
                    index += 1
                    retries = 0
                    update_pointer.execute(session_id, index, "asking", retries)
                    current_turn.fsm.transition_to(ConversationState.NEXT_TURN, reason="Advancing pointer")
                    if not await ask_current():
                        break
                else:
                    pl.turn_retry(session_id, bound_turn_id, index, retries + 1)
                    current_turn.fsm.transition_to(ConversationState.RETRY, reason="Follow-up / retry required")
                    retries += 1
                    update_pointer.execute(session_id, index, "repeating", retries)
                    # The LLM's streaming response already spoke the follow-up/clarification.
                    # Just drain stale STT and wait for the user's next answer.
                    if current_turn and not current_turn.is_destroyed:
                        new_epoch = stt_adapter.advance_epoch()
                        runtime_state.advance_epoch(session_id)
                        current_turn.listening_epoch = new_epoch
                        await stt_adapter.drain_before(new_epoch)
                        pl.stt_epoch_advance(session_id, bound_turn_id, new_epoch)
                        if current_turn.fsm.current_state != ConversationState.LISTENING:
                            current_turn.fsm.transition_to(ConversationState.LISTENING, reason="LLM follow-up spoken — listening for answer")
                continue

            logger.info(f"[INTERRUPT NONE] Discarding unintelligible utterance: '{transcript[:60]}'")

    except (WebSocketDisconnect, RuntimeError) as e:
        err = classify_error("connection_lost", str(e))
        logger.warning(f"[WS ERROR/DISCONNECT] {err.category.value} session_id={session_id}: {e}")
        pause_session.execute(session_id)
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
