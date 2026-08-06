"""Speech provider management endpoints."""

import json
import urllib.request
import urllib.error
import asyncio
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from app.modules.provider.infrastructure.persistence.postgres_speech_provider_repository import PostgresSpeechProviderRepository
from app.shared.security.envelope_encryption import encrypt_and_store, load_and_decrypt

router = APIRouter(prefix="/speech-providers", tags=["speech-providers"])
_repo = PostgresSpeechProviderRepository()


class SpeechProviderCreateRequest(BaseModel):
    name: str
    provider_type: str  # 'deepgram' | 'elevenlabs'
    credentials: Dict[str, Any]  # plaintext {"api_key": "..."}
    stt_model: str = ""
    stt_language: str = "en"
    stt_extra: Dict[str, Any] = {}
    tts_model: str = ""
    tts_voice_id: str = ""
    tts_extra: Dict[str, Any] = {}


class SpeechProviderUpdateRequest(BaseModel):
    name: Optional[str] = None
    provider_type: Optional[str] = None
    credentials: Optional[Dict[str, Any]] = None
    stt_model: Optional[str] = None
    stt_language: Optional[str] = None
    stt_extra: Optional[Dict[str, Any]] = None
    tts_model: Optional[str] = None
    tts_voice_id: Optional[str] = None
    tts_extra: Optional[Dict[str, Any]] = None


class SpeechModelFetchRequest(BaseModel):
    provider_id: Optional[str] = None
    provider_type: Optional[str] = None
    api_key: Optional[str] = ""


class SampleAudioRequest(BaseModel):
    provider_id: Optional[str] = None
    provider_type: Optional[str] = None
    api_key: Optional[str] = ""
    tts_model: Optional[str] = ""
    tts_voice_id: Optional[str] = ""
    text: Optional[str] = "Hey, how's it going!"


DEEPGRAM_STT_MODELS = [
    {"id": "flux", "name": "Flux (Ultra-Fast Conversational STT & Agent Loop)"},
    {"id": "nova-3", "name": "Nova-3 / Flux (Latest Ultra-Fast & High Accuracy)"},
    {"id": "nova-3-general", "name": "Nova-3 General"},
    {"id": "nova-3-conversationalai", "name": "Nova-3 Conversational AI"},
    {"id": "nova-3-medical", "name": "Nova-3 Medical"},
    {"id": "nova-2", "name": "Nova-2 (Fast & Reliable)"},
    {"id": "nova-2-general", "name": "Nova-2 General"},
    {"id": "nova-2-meeting", "name": "Nova-2 Meeting"},
    {"id": "nova-2-phonecall", "name": "Nova-2 Phone Call"},
    {"id": "nova-2-finance", "name": "Nova-2 Finance"},
    {"id": "nova-2-conversationalai", "name": "Nova-2 Conversational AI"},
    {"id": "nova-2-medical", "name": "Nova-2 Medical"},
    {"id": "nova", "name": "Nova v1"},
    {"id": "enhanced", "name": "Enhanced"},
    {"id": "base", "name": "Base"},
]

DEEPGRAM_TTS_MODELS = [
    {"id": "flux-rufus-en", "name": "Flux Rufus (Conversational Male - Flux v2)"},
    {"id": "aura-asteria-en", "name": "Aura Asteria (US Female - Aura v1)"},
    {"id": "aura-stella-en", "name": "Aura Stella (US Female - Aura v1)"},
    {"id": "aura-athena-en", "name": "Aura Athena (UK Female - Aura v1)"},
    {"id": "aura-hera-en", "name": "Aura Hera (US Female - Aura v1)"},
    {"id": "aura-luna-en", "name": "Aura Luna (US Female - Aura v1)"},
    {"id": "aura-orion-en", "name": "Aura Orion (US Male - Aura v1)"},
    {"id": "aura-arcas-en", "name": "Aura Arcas (US Male - Aura v1)"},
    {"id": "aura-perseus-en", "name": "Aura Perseus (US Male - Aura v1)"},
    {"id": "aura-angus-en", "name": "Aura Angus (UK Male - Aura v1)"},
    {"id": "aura-orpheus-en", "name": "Aura Orpheus (US Male - Aura v1)"},
    {"id": "aura-helios-en", "name": "Aura Helios (UK Male - Aura v1)"},
    {"id": "aura-zeus-en", "name": "Aura Zeus (US Male - Aura v1)"},
]

ELEVENLABS_FALLBACK_MODELS = [
    {"id": "eleven_flash_v2_5", "name": "Eleven Flash v2.5 (75ms Ultra-Low Latency Streaming)"},
    {"id": "eleven_turbo_v2_5", "name": "Eleven Turbo v2.5 (Low Latency Real-time TTS)"},
    {"id": "eleven_multilingual_v2", "name": "Eleven Multilingual v2 (High Quality Conversational)"},
    {"id": "eleven_multilingual_v1", "name": "Eleven Multilingual v1"},
    {"id": "eleven_monolingual_v1", "name": "Eleven Monolingual v1"},
]

ELEVENLABS_FALLBACK_VOICES = [
    {"id": "21m00Tcm4TlvDq8ikWAM", "name": "Rachel (Expressive Female)"},
    {"id": "AZnzlk1XvdvUeBnXmlld", "name": "Domi (Confident Female)"},
    {"id": "EXAVITQu4vr4xnSDxMaL", "name": "Bella (Warm Female)"},
    {"id": "ErXwobaYiN019PkySvjV", "name": "Antoni (Friendly Male)"},
    {"id": "MF3mGyEYCl7XYWbV9V6O", "name": "Elli (Soft Female)"},
    {"id": "TxGEqnHWrfWFTfGW9XjX", "name": "Josh (Conversational Male)"},
    {"id": "VR6AewLTigWG4xSOukaG", "name": "Arnold (Deep Male)"},
    {"id": "pNInz6obpgDQGcFmaJgB", "name": "Adam (Clear Male)"},
    {"id": "yoZ06aMxZJJ28mfd3POQ", "name": "Sam (Dynamic Male)"},
]


def _fetch_elevenlabs_data_sync(api_key: str):
    models = ELEVENLABS_FALLBACK_MODELS
    voices = []
    if not api_key:
        return models, voices, False

    # Fetch dynamic voices
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/voices",
        headers={"xi-api-key": api_key, "Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        for v in data.get("voices", []):
            name = v.get("name", "Voice")
            cat = v.get("category")
            if cat:
                name = f"{name} ({cat})"
            voices.append({"id": v["voice_id"], "name": name})

    return models, voices, True


def _fetch_deepgram_data_sync(api_key: str):
    stt_models = []
    tts_models = []

    if not api_key:
        return stt_models, tts_models, False

    req = urllib.request.Request(
        "https://api.deepgram.com/v1/models",
        headers={"Authorization": f"Token {api_key}", "Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        stt_raw = data.get("stt") or data.get("models") or []
        if isinstance(stt_raw, list):
            for m in stt_raw:
                if isinstance(m, dict):
                    mid = m.get("canonical_name") or m.get("name") or m.get("id") or ""
                    name = m.get("name") or mid
                    arch = m.get("architecture") or ""
                    if mid:
                        stt_models.append({"id": mid, "name": f"{name} ({arch})"})

        tts_raw = data.get("tts") or []
        if isinstance(tts_raw, list):
            for m in tts_raw:
                if isinstance(m, dict):
                    mid = m.get("canonical_name") or m.get("name") or m.get("id") or ""
                    name = m.get("name") or mid
                    arch = m.get("architecture") or ""
                    if mid:
                        tts_models.append({"id": mid, "name": f"{name} ({arch})"})

    return stt_models, tts_models, True


def _generate_sample_audio_sync(req: SampleAudioRequest) -> tuple[bytes, str]:
    text = req.text or "Hey, how's it going!"
    api_key = req.api_key or ""
    provider_type = req.provider_type or "deepgram"

    if provider_type == "elevenlabs":
        voice_id = req.tts_voice_id or "21m00Tcm4TlvDq8ikWAM"
        model_id = req.tts_model or "eleven_turbo_v2_5"
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128"
        payload = json.dumps({"text": text, "model_id": model_id}).encode("utf-8")
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=10) as response:
            audio_bytes = response.read()
            return audio_bytes, "audio/mpeg"
    else:  # Deepgram
        model = req.tts_model or "aura-asteria-en"
        primary_v = "v2" if model.lower().startswith("flux") else "v1"
        fallback_v = "v1" if primary_v == "v2" else "v2"

        alt_model = model
        if model.lower().startswith("flux-"):
            alt_model = "aura-" + model[5:]
        elif model.lower().startswith("aura-"):
            alt_model = "flux-" + model[5:]

        payload = json.dumps({"text": text}).encode("utf-8")
        headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
            "Accept": "audio/wav",
        }

        attempts = [
            (primary_v, model),
            (fallback_v, model),
            (primary_v, alt_model),
            (fallback_v, alt_model),
        ]

        last_err = None
        for version, m_name in attempts:
            try:
                url = f"https://api.deepgram.com/{version}/speak?model={m_name}&encoding=linear16&sample_rate=24000"
                request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
                with urllib.request.urlopen(request, timeout=10) as response:
                    audio_bytes = response.read()
                    return audio_bytes, "audio/wav"
            except Exception as e:
                last_err = e
                continue

        if last_err:
            raise last_err


@router.get("")
async def list_speech_providers():
    providers = await _repo.list_all()
    for p in providers:
        p["credentials_enc"] = {"encrypted": True}
    return providers


@router.post("/fetch-models")
async def fetch_speech_models(req: SpeechModelFetchRequest):
    api_key = req.api_key or ""
    provider_type = req.provider_type or "deepgram"

    if req.provider_id:
        p = await _repo.get_by_id(req.provider_id)
        if p and p.get("credentials_enc") and p.get("key_version"):
            provider_type = p.get("provider_type") or provider_type
            creds = await load_and_decrypt(p["credentials_enc"], p["key_version"])
            if not api_key:
                api_key = creds.get("api_key", "")

    if not api_key:
        raise HTTPException(status_code=400, detail="API Key is required to fetch models")

    try:
        if provider_type == "elevenlabs":
            models, voices, is_valid = await asyncio.to_thread(_fetch_elevenlabs_data_sync, api_key)
            final_tts_models = models if models else ELEVENLABS_FALLBACK_MODELS
            final_tts_voices = voices if voices else ELEVENLABS_FALLBACK_VOICES
            return {
                "stt_models": [
                    {"id": "scribe_v1", "name": "Scribe v1 (High Accuracy Real-time STT)"},
                    {"id": "scribe_v1_base", "name": "Scribe v1 Base STT"},
                ],
                "tts_models": final_tts_models,
                "tts_voices": final_tts_voices,
                "fetched": is_valid,
            }
        else:  # Deepgram
            live_stt, live_tts, is_valid = await asyncio.to_thread(_fetch_deepgram_data_sync, api_key)
            
            stt_map = {m["id"]: m for m in DEEPGRAM_STT_MODELS}
            for m in live_stt:
                stt_map[m["id"]] = m

            tts_map = {m["id"]: m for m in DEEPGRAM_TTS_MODELS}
            for m in live_tts:
                tts_map[m["id"]] = m

            return {
                "stt_models": list(stt_map.values()),
                "tts_models": list(tts_map.values()),
                "tts_voices": list(tts_map.values()),
                "fetched": is_valid,
            }
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        if e.code == 401:
            raise HTTPException(status_code=401, detail="Invalid API Key: 401 Unauthorized from speech provider.")
        raise HTTPException(status_code=e.code, detail=f"Provider API Error ({e.code}): {err_body[:200]}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to connect to speech provider: {str(e)}")


@router.post("/sample-audio")
async def generate_sample_audio(req: SampleAudioRequest):
    api_key = req.api_key or ""
    provider_type = req.provider_type or "deepgram"

    if req.provider_id:
        p = await _repo.get_by_id(req.provider_id)
        if p and p.get("credentials_enc") and p.get("key_version"):
            provider_type = p.get("provider_type") or provider_type
            creds = await load_and_decrypt(p["credentials_enc"], p["key_version"])
            if not api_key:
                api_key = creds.get("api_key", "")

    req.api_key = api_key
    req.provider_type = provider_type

    if not req.api_key:
        raise HTTPException(status_code=400, detail="API Key is required to generate live voice preview")
    try:
        audio_bytes, media_type = await asyncio.to_thread(_generate_sample_audio_sync, req)
        return Response(content=audio_bytes, media_type=media_type)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        if e.code == 401:
            raise HTTPException(status_code=401, detail="Saved API key returned 401 Unauthorized from provider. Please enter a valid API key.")
        raise HTTPException(status_code=e.code, detail=f"Provider API Error ({e.code}): {err_body[:200]}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate live audio sample: {str(e)}")


@router.post("")
async def create_speech_provider(req: SpeechProviderCreateRequest):
    blob, key_version = await encrypt_and_store(req.credentials)
    provider_data = {
        "name": req.name,
        "provider_type": req.provider_type,
        "credentials_enc": blob,
        "key_version": key_version,
        "stt_model": req.stt_model,
        "stt_language": req.stt_language,
        "stt_extra": req.stt_extra,
        "tts_model": req.tts_model,
        "tts_voice_id": req.tts_voice_id,
        "tts_extra": req.tts_extra,
    }
    pid = await _repo.create(provider_data)
    return {"id": pid, "status": "created"}


@router.get("/{provider_id}")
async def get_speech_provider(provider_id: str):
    provider = await _repo.get_by_id(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Speech provider not found")
    provider["credentials_enc"] = {"encrypted": True}
    return provider


@router.put("/{provider_id}")
async def update_speech_provider(provider_id: str, req: SpeechProviderUpdateRequest):
    existing = await _repo.get_by_id(provider_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Speech provider not found")

    updates = {}
    for k, v in req.model_dump().items():
        if v is not None and k != "credentials":
            updates[k] = v

    if req.credentials and req.credentials.get("api_key"):
        blob, key_version = await encrypt_and_store(req.credentials)
        updates["credentials_enc"] = blob
        updates["key_version"] = key_version

    await _repo.update(provider_id, updates)
    return {"status": "updated"}


@router.delete("/{provider_id}")
async def delete_speech_provider(provider_id: str):
    existing = await _repo.get_by_id(provider_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Speech provider not found")
    await _repo.delete(provider_id)
    return {"status": "deleted"}
