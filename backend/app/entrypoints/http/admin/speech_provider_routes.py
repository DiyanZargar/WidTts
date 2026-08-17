"""Speech provider management endpoints."""

import json
import urllib.request
import urllib.error
import asyncio
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from app.modules.provider.infrastructure.persistence.speech_provider_repository import SpeechProviderRepository
from app.shared.security.envelope_encryption import encrypt_and_store, load_and_decrypt
from app.shared.constants.provider_urls import ELEVENLABS_API_URL, DEEPGRAM_API_URL, FISH_AUDIO_API_URL
from app.shared.constants.model_catalogs import (
    DEEPGRAM_STT_MODELS, DEEPGRAM_TTS_MODELS,
    ELEVENLABS_FALLBACK_MODELS, ELEVENLABS_FALLBACK_VOICES,
)

router = APIRouter(prefix="/speech-providers", tags=["speech-providers"])
_repo = SpeechProviderRepository()


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
    {"id": "nova-3", "name": "Nova-3 / Flux (Latest Ultra-Fast & High Accuracy)"},
    {"id": "nova-3-general", "name": "Nova-3 General"},

def _fetch_elevenlabs_data_sync(api_key: str):
    models = ELEVENLABS_FALLBACK_MODELS
    voices = []
    if not api_key:
        return models, voices, False

    # Fetch dynamic voices
    req = urllib.request.Request(
        f"{ELEVENLABS_API_URL}/voices",
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
        f"{DEEPGRAM_API_URL}/v1/models",
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


def _fetch_fish_models_sync(api_key: str):
    """Fetch voices from Fish Audio's voice library API.

    Returns (tts_models, tts_voices, is_valid).
    Fish Audio has no STT — STT models list is always empty.
    tts_voices include language info for frontend grouping.
    """
    tts_models = [
        {"id": "s2.1-pro", "name": "S2.1 Pro (83 Languages, Recommended)"},
        {"id": "s2.1-pro-free", "name": "S2.1 Pro Free (83 Languages)"},
        {"id": "s2-pro", "name": "S2 Pro (80+ Languages)"},
        {"id": "s1", "name": "S1 (13 Languages)"},
    ]
    voices = []

    if not api_key:
        return tts_models, voices, False

    # Fetch all voices from Fish Audio voice library (no language filter)
    try:
        req = urllib.request.Request(
            f"{FISH_AUDIO_API_URL}/model?page_size=100",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            items = data.get("items") or data.get("data") or []
            seen = set()
            for v in items:
                vid = v.get("_id") or v.get("id") or ""
                name = v.get("title") or v.get("name") or "Voice"
                lang = v.get("language") or "en"
                # Deduplicate by voice ID
                if vid and vid not in seen:
                    seen.add(vid)
                    voices.append({"id": vid, "name": name, "language": lang})
    except Exception:
        pass  # voice fetch is best-effort

    return tts_models, voices, True


from collections import OrderedDict

_SAMPLE_AUDIO_CACHE: OrderedDict[tuple[str, str, str, str], tuple[bytes, str]] = OrderedDict()
_SAMPLE_AUDIO_CACHE_MAX = 50  # Max cached audio samples


def _cache_get(key: tuple[str, str, str, str]) -> tuple[bytes, str] | None:
    if key in _SAMPLE_AUDIO_CACHE:
        _SAMPLE_AUDIO_CACHE.move_to_end(key)
        return _SAMPLE_AUDIO_CACHE[key]
    return None


def _cache_set(key: tuple[str, str, str, str], value: tuple[bytes, str]) -> None:
    _SAMPLE_AUDIO_CACHE[key] = value
    _SAMPLE_AUDIO_CACHE.move_to_end(key)
    while len(_SAMPLE_AUDIO_CACHE) > _SAMPLE_AUDIO_CACHE_MAX:
        _SAMPLE_AUDIO_CACHE.popitem(last=False)


def _generate_sample_audio_sync(req: SampleAudioRequest) -> tuple[bytes, str]:
    text = req.text or "Hey, how's it going!"
    api_key = req.api_key or ""
    provider_type = req.provider_type or "deepgram"
    model = req.tts_model or ""
    voice_id = req.tts_voice_id or ""

    cache_key = (provider_type, model, voice_id, text)
    cached = _cache_get(cache_key)
    if cached:
        return cached

    if provider_type == "elevenlabs":
        # Detect if model is actually a 20-char voice ID (e.g. EXAVITQu4vr4xnSDxMaL)
        if model and len(model) == 20 and model.isalnum() and not model.startswith("eleven_") and not model.startswith("scribe_"):
            voice_id = model
            model = ""
        # Default working voice: Sarah (EXAVITQu4vr4xnSDxMaL) which works on free tier
        voice_id = voice_id or "EXAVITQu4vr4xnSDxMaL"
        model_id = model if (model and model.startswith("eleven_")) else "eleven_turbo_v2_5"
        url = f"{ELEVENLABS_API_URL}/text-to-speech/{voice_id}?output_format=mp3_44100_128"
        el_payload = json.dumps({"text": text, "model_id": model_id}).encode("utf-8")
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        request = urllib.request.Request(url, data=el_payload, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=5) as response:
            audio_bytes = response.read()
            res = (audio_bytes, "audio/mpeg")
            _cache_set(cache_key, res)
            return res
    elif provider_type == "fishaudio":
        # Detect if model is actually a 24-char hex voice profile ID
        if model and len(model) == 24 and all(c in "0123456789abcdef" for c in model.lower()):
            voice_id = model
            model = ""
        target_model = model if (model and not len(model) == 24) else "s2.1-pro"
        fa_payload: Dict[str, Any] = {"text": text}
        if voice_id:
            fa_payload["reference_id"] = voice_id
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "model": target_model,
        }
        data_bytes = json.dumps(fa_payload).encode("utf-8")
        request = urllib.request.Request(
            f"{FISH_AUDIO_API_URL}/v1/tts",
            data=data_bytes,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            audio_bytes = response.read()
            res = (audio_bytes, "audio/mpeg")
            _cache_set(cache_key, res)
            return res
    else:  # Deepgram REST (Real Neural Voice)
        target_model = model or "aura-asteria-en"

        # Flux → Aura-1 mapping (Flux models are streaming-only, map to REST equivalents)
        flux_map = {
            "flux-rufus-en": "aura-orion-en",
            "flux-aura-en": "aura-asteria-en",
            "flux-asteria-en": "aura-asteria-en",
            "flux-orion-en": "aura-orion-en",
            "flux-luna-en": "aura-luna-en",
            "flux-arcas-en": "aura-arcas-en",
            "flux-stella-en": "aura-stella-en",
            "flux-athena-en": "aura-athena-en",
            "flux-helios-en": "aura-helios-en",
            "flux-zeus-en": "aura-zeus-en",
        }

        # Determine the best API version per model family (from dev branch)
        primary_v = "v2" if target_model.lower().startswith("flux") else "v1"
        fallback_v = "v1" if primary_v == "v2" else "v2"

        # Build mapped alternative model name
        alt_model = ""
        if target_model.lower() in flux_map:
            alt_model = flux_map[target_model.lower()]
        elif target_model.lower().startswith("flux-"):
            alt_model = "aura-" + target_model[5:]
        elif target_model.lower().startswith("aura-"):
            alt_model = "flux-" + target_model[5:]

        # Build attempt list: primary version + model first, then fallbacks
        attempts = [
            (primary_v, target_model),
            (fallback_v, target_model),
        ]
        if alt_model:
            alt_v = "v2" if alt_model.lower().startswith("flux") else "v1"
            attempts.append((alt_v, alt_model))
        attempts.extend([
            ("v2", "flux-rufus-en"),
            ("v1", "aura-asteria-en"),
            ("v1", "aura-orion-en"),
        ])

        dg_payload = json.dumps({"text": text}).encode("utf-8")
        headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
            "Accept": "audio/wav",
        }

        last_err = None
        for version, m_name in attempts:
            if not m_name:
                continue
            try:
                url = f"{DEEPGRAM_API_URL}/{version}/speak?model={m_name}&encoding=linear16&sample_rate=24000"
                request = urllib.request.Request(url, data=dg_payload, headers=headers, method="POST")
                with urllib.request.urlopen(request, timeout=10) as response:
                    audio_bytes = response.read()
                    res = (audio_bytes, "audio/wav")
                    _cache_set(cache_key, res)
                    return res
            except Exception as e:
                last_err = e
                continue

        if last_err:
            raise last_err
        raise ValueError(f"Failed to generate sample audio for provider {provider_type}")


def _prewarm_models_background(api_key: str, provider_type: str, models: List[str]):
    for m in models:
        try:
            req = SampleAudioRequest(api_key=api_key, provider_type=provider_type, tts_model=m)
            _generate_sample_audio_sync(req)
        except Exception:
            pass


async def _trigger_prewarm(api_key: str, provider_type: str, models: List[str]):
    await asyncio.to_thread(_prewarm_models_background, api_key, provider_type, models)


@router.get("")
async def list_speech_providers():
    providers = await _repo.list_all()
    for p in providers:
        if p.get("credentials_enc") and p.get("key_version"):
            try:
                creds = await load_and_decrypt(p["credentials_enc"], p["key_version"])
                api_key = creds.get("api_key", "")
                if api_key:
                    ptype = p.get("provider_type") or "deepgram"
                    # Only prewarm Deepgram — model names are Deepgram-specific
                    if ptype == "deepgram":
                        asyncio.create_task(_trigger_prewarm(api_key, ptype, ["flux-rufus-en", "flux-aura-en", "aura-asteria-en", "aura-orion-en"]))
            except Exception:
                pass
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
        elif provider_type == "fishaudio":
            tts_models, voices, is_valid = await asyncio.to_thread(_fetch_fish_models_sync, api_key)
            return {
                "stt_models": [],
                "tts_models": tts_models,
                "tts_voices": voices,
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


class PrewarmRequest(BaseModel):
    provider_id: str
    models: List[str]


@router.post("/prewarm")
async def prewarm_models(req: PrewarmRequest):
    """Fire-and-forget: prewarm all listed TTS models in the backend cache."""
    p = await _repo.get_by_id(req.provider_id)
    if not p or not p.get("credentials_enc") or not p.get("key_version"):
        return {"status": "skipped", "reason": "provider not found or no credentials"}

    try:
        creds = await load_and_decrypt(p["credentials_enc"], p["key_version"])
        api_key = creds.get("api_key", "")
        provider_type = p.get("provider_type") or "deepgram"
        if api_key:
            asyncio.create_task(_trigger_prewarm(api_key, provider_type, req.models))
    except Exception:
        pass
    return {"status": "prewarming", "models": len(req.models)}


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
    # Check if any deployed bot references this provider
    from app.modules.bot.infrastructure.persistence.bot_repository import BotRepository
    bot_repo = BotRepository()
    bots = await bot_repo.list_all()
    using_bots = [b["name"] for b in bots if b.get("is_deployed") and (b.get("stt_provider_id") == provider_id or b.get("tts_provider_id") == provider_id)]
    if using_bots:
        raise HTTPException(status_code=409, detail=f"Cannot delete — used by deployed bot(s): {', '.join(using_bots)}. Undeploy them first.")
    await _repo.delete(provider_id)
    return {"status": "deleted"}
