"""Bot management endpoints."""

import re
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.modules.bot.infrastructure.persistence.postgres_bot_repository import PostgresBotRepository

router = APIRouter(prefix="/bots", tags=["bots"])
_repo = PostgresBotRepository()


def _generate_slug(name: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower().strip())
    slug = slug.strip('-')
    return slug or "bot"


class BotCreateRequest(BaseModel):
    name: str
    description: str = ""
    personality: str = ""
    system_prompt: str = ""
    llm_provider_id: Optional[str] = None
    llm_model: str = ""
    stt_provider_id: Optional[str] = None
    tts_provider_id: Optional[str] = None
    stt_model: str = ""
    tts_model: str = ""
    stt_languages: List[str] = ["en"]
    stt_primary_language: str = "en"
    tts_languages: List[str] = ["en"]
    tts_primary_language: str = "en"


class BotUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    personality: Optional[str] = None
    system_prompt: Optional[str] = None
    llm_provider_id: Optional[str] = None
    llm_model: Optional[str] = None
    stt_provider_id: Optional[str] = None
    tts_provider_id: Optional[str] = None
    stt_model: Optional[str] = None
    tts_model: Optional[str] = None
    stt_languages: Optional[List[str]] = None
    stt_primary_language: Optional[str] = None
    tts_languages: Optional[List[str]] = None
    tts_primary_language: Optional[str] = None


@router.get("")
async def list_bots():
    return await _repo.list_all()


@router.post("")
async def create_bot(req: BotCreateRequest):
    bot_id = await _repo.create(req.model_dump())
    await _repo.activate(bot_id)
    return {"id": bot_id, "status": "created"}


@router.get("/active")
async def get_active_bot():
    bot = await _repo.get_active()
    if not bot:
        return {"active": None}
    return bot


@router.get("/speech-models/{provider_type}")
async def list_speech_models(provider_type: str):
    return _get_speech_models(provider_type)


@router.get("/{bot_id}")
async def get_bot(bot_id: str):
    bot = await _repo.get_by_id(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    return bot


@router.put("/{bot_id}")
async def update_bot(bot_id: str, req: BotUpdateRequest):
    existing = await _repo.get_by_id(bot_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Bot not found")
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    await _repo.update(bot_id, updates)
    await _repo.activate(bot_id)
    return {"status": "updated"}


@router.delete("/{bot_id}")
async def delete_bot(bot_id: str):
    existing = await _repo.get_by_id(bot_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Bot not found")
    if existing.get("is_deployed"):
        raise HTTPException(status_code=409, detail=f"Cannot delete \"{existing.get('name', 'bot')}\" — it is currently deployed. Undeploy it first.")
    await _repo.delete(bot_id)
    return {"status": "deleted"}


@router.post("/{bot_id}/activate")
async def activate_bot(bot_id: str):
    existing = await _repo.get_by_id(bot_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Bot not found")
    await _repo.activate(bot_id)
    return {"status": "activated", "bot_id": bot_id}


@router.post("/{bot_id}/deploy")
async def deploy_bot(bot_id: str):
    existing = await _repo.get_by_id(bot_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Bot not found")
    if existing.get("is_deployed") and existing.get("deploy_slug"):
        return {"status": "deployed", "bot_id": bot_id, "slug": existing["deploy_slug"], "url": f"/bot/{existing['deploy_slug']}"}
    base_slug = _generate_slug(existing.get("name", "bot"))
    slug = base_slug
    suffix = 1
    while True:
        if not await _repo.get_by_slug(slug):
            break
        suffix += 1
        slug = f"{base_slug}-{suffix}"
    await _repo.deploy(bot_id, slug)
    return {"status": "deployed", "bot_id": bot_id, "slug": slug, "url": f"/bot/{slug}"}


@router.post("/{bot_id}/undeploy")
async def undeploy_bot(bot_id: str):
    existing = await _repo.get_by_id(bot_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Bot not found")
    await _repo.undeploy(bot_id)
    return {"status": "undeployed", "bot_id": bot_id}


def _get_speech_models(provider_type: str) -> dict:
    """Return STT/TTS models grouped by language for the given provider.
    
    Language is parsed dynamically from model names using the Deepgram
    convention: [family]-[voice]-[language_code]. This means new voices
    added by Deepgram will automatically appear under the correct language
    without code changes.
    """
    if provider_type == "deepgram":
        # All Deepgram Aura-2 + Aura-1 + Flux voices
        # Format: [family]-[voice]-[lang] — language parsed from last segment
        tts_voices = [
            # Flux voices (conversational)
            {"id": "flux-aura-en", "name": "Flux Aura"},
            {"id": "flux-rufus-en", "name": "Flux Rufus"},
            # Aura-1 voices
            {"id": "aura-asteria-en", "name": "Aura Asteria"},
            {"id": "aura-orion-en", "name": "Aura Orion"},
            {"id": "aura-luna-en", "name": "Aura Luna"},
            {"id": "aura-arcas-en", "name": "Aura Arcas"},
            {"id": "aura-stella-en", "name": "Aura Stella"},
            {"id": "aura-athena-en", "name": "Aura Athena"},
            {"id": "aura-helios-en", "name": "Aura Helios"},
            {"id": "aura-zeus-en", "name": "Aura Zeus"},
            # Aura-2 English
            {"id": "aura-2-amalthea-en", "name": "Aura 2 Amalthea"},
            {"id": "aura-2-andromeda-en", "name": "Aura 2 Andromeda"},
            {"id": "aura-2-apollo-en", "name": "Aura 2 Apollo"},
            {"id": "aura-2-arcas-en", "name": "Aura 2 Arcas"},
            {"id": "aura-2-aries-en", "name": "Aura 2 Aries"},
            {"id": "aura-2-asteria-en", "name": "Aura 2 Asteria"},
            {"id": "aura-2-athena-en", "name": "Aura 2 Athena"},
            {"id": "aura-2-atlas-en", "name": "Aura 2 Atlas"},
            {"id": "aura-2-aurora-en", "name": "Aura 2 Aurora"},
            {"id": "aura-2-callista-en", "name": "Aura 2 Callista"},
            {"id": "aura-2-cora-en", "name": "Aura 2 Cora"},
            {"id": "aura-2-cordelia-en", "name": "Aura 2 Cordelia"},
            {"id": "aura-2-delia-en", "name": "Aura 2 Delia"},
            {"id": "aura-2-draco-en", "name": "Aura 2 Draco"},
            {"id": "aura-2-electra-en", "name": "Aura 2 Electra"},
            {"id": "aura-2-harmonia-en", "name": "Aura 2 Harmonia"},
            {"id": "aura-2-helena-en", "name": "Aura 2 Helena"},
            {"id": "aura-2-hera-en", "name": "Aura 2 Hera"},
            {"id": "aura-2-hermes-en", "name": "Aura 2 Hermes"},
            {"id": "aura-2-hyperion-en", "name": "Aura 2 Hyperion"},
            {"id": "aura-2-iris-en", "name": "Aura 2 Iris"},
            {"id": "aura-2-janus-en", "name": "Aura 2 Janus"},
            {"id": "aura-2-juno-en", "name": "Aura 2 Juno"},
            {"id": "aura-2-jupiter-en", "name": "Aura 2 Jupiter"},
            {"id": "aura-2-luna-en", "name": "Aura 2 Luna"},
            {"id": "aura-2-mars-en", "name": "Aura 2 Mars"},
            {"id": "aura-2-minerva-en", "name": "Aura 2 Minerva"},
            {"id": "aura-2-neptune-en", "name": "Aura 2 Neptune"},
            {"id": "aura-2-odysseus-en", "name": "Aura 2 Odysseus"},
            {"id": "aura-2-ophelia-en", "name": "Aura 2 Ophelia"},
            {"id": "aura-2-orion-en", "name": "Aura 2 Orion"},
            {"id": "aura-2-orpheus-en", "name": "Aura 2 Orpheus"},
            {"id": "aura-2-pandora-en", "name": "Aura 2 Pandora"},
            {"id": "aura-2-phoebe-en", "name": "Aura 2 Phoebe"},
            {"id": "aura-2-pluto-en", "name": "Aura 2 Pluto"},
            {"id": "aura-2-saturn-en", "name": "Aura 2 Saturn"},
            {"id": "aura-2-selene-en", "name": "Aura 2 Selene"},
            {"id": "aura-2-thalia-en", "name": "Aura 2 Thalia"},
            {"id": "aura-2-theia-en", "name": "Aura 2 Theia"},
            {"id": "aura-2-vesta-en", "name": "Aura 2 Vesta"},
            {"id": "aura-2-zeus-en", "name": "Aura 2 Zeus"},
            # Aura-2 Spanish
            {"id": "aura-2-sirio-es", "name": "Aura 2 Sirio"},
            {"id": "aura-2-nestor-es", "name": "Aura 2 Nestor"},
            {"id": "aura-2-carina-es", "name": "Aura 2 Carina"},
            {"id": "aura-2-celeste-es", "name": "Aura 2 Celeste"},
            {"id": "aura-2-alvaro-es", "name": "Aura 2 Alvaro"},
            {"id": "aura-2-diana-es", "name": "Aura 2 Diana"},
            {"id": "aura-2-aquila-es", "name": "Aura 2 Aquila"},
            {"id": "aura-2-selena-es", "name": "Aura 2 Selena"},
            {"id": "aura-2-estrella-es", "name": "Aura 2 Estrella"},
            {"id": "aura-2-javier-es", "name": "Aura 2 Javier"},
            {"id": "aura-2-agustina-es", "name": "Aura 2 Agustina"},
            {"id": "aura-2-antonia-es", "name": "Aura 2 Antonia"},
            {"id": "aura-2-gloria-es", "name": "Aura 2 Gloria"},
            {"id": "aura-2-luciano-es", "name": "Aura 2 Luciano"},
            {"id": "aura-2-olivia-es", "name": "Aura 2 Olivia"},
            {"id": "aura-2-silvia-es", "name": "Aura 2 Silvia"},
            {"id": "aura-2-valerio-es", "name": "Aura 2 Valerio"},
            # Aura-2 Dutch
            {"id": "aura-2-beatrix-nl", "name": "Aura 2 Beatrix"},
            {"id": "aura-2-daphne-nl", "name": "Aura 2 Daphne"},
            {"id": "aura-2-cornelia-nl", "name": "Aura 2 Cornelia"},
            {"id": "aura-2-sander-nl", "name": "Aura 2 Sander"},
            {"id": "aura-2-hestia-nl", "name": "Aura 2 Hestia"},
            {"id": "aura-2-lars-nl", "name": "Aura 2 Lars"},
            {"id": "aura-2-roman-nl", "name": "Aura 2 Roman"},
            {"id": "aura-2-rhea-nl", "name": "Aura 2 Rhea"},
            {"id": "aura-2-leda-nl", "name": "Aura 2 Leda"},
            # Aura-2 French
            {"id": "aura-2-agathe-fr", "name": "Aura 2 Agathe"},
            {"id": "aura-2-hector-fr", "name": "Aura 2 Hector"},
            # Aura-2 German
            {"id": "aura-2-elara-de", "name": "Aura 2 Elara"},
            {"id": "aura-2-aurelia-de", "name": "Aura 2 Aurelia"},
            {"id": "aura-2-lara-de", "name": "Aura 2 Lara"},
            {"id": "aura-2-julius-de", "name": "Aura 2 Julius"},
            {"id": "aura-2-fabian-de", "name": "Aura 2 Fabian"},
            {"id": "aura-2-kara-de", "name": "Aura 2 Kara"},
            {"id": "aura-2-viktoria-de", "name": "Aura 2 Viktoria"},
            # Aura-2 Italian
            {"id": "aura-2-melia-it", "name": "Aura 2 Melia"},
            {"id": "aura-2-elio-it", "name": "Aura 2 Elio"},
            {"id": "aura-2-flavio-it", "name": "Aura 2 Flavio"},
            {"id": "aura-2-maia-it", "name": "Aura 2 Maia"},
            {"id": "aura-2-cinzia-it", "name": "Aura 2 Cinzia"},
            {"id": "aura-2-cesare-it", "name": "Aura 2 Cesare"},
            {"id": "aura-2-livia-it", "name": "Aura 2 Livia"},
            {"id": "aura-2-perseo-it", "name": "Aura 2 Perseo"},
            {"id": "aura-2-dionisio-it", "name": "Aura 2 Dionisio"},
            {"id": "aura-2-demetra-it", "name": "Aura 2 Demetra"},
            # Aura-2 Japanese
            {"id": "aura-2-fujin-ja", "name": "Aura 2 Fujin"},
            {"id": "aura-2-izanami-ja", "name": "Aura 2 Izanami"},
        ]

        # Dynamically parse language from model name: [family]-[voice]-[lang]
        # Complete language name map from Deepgram docs
        lang_names = {
            "en": "English", "es": "Spanish", "nl": "Dutch", "fr": "French",
            "de": "German", "it": "Italian", "ja": "Japanese", "ko": "Korean",
            "pt": "Portuguese", "zh": "Chinese", "ar": "Arabic", "hi": "Hindi",
            "ru": "Russian", "tr": "Turkish", "pl": "Polish", "sv": "Swedish",
            "no": "Norwegian", "da": "Danish", "fi": "Finnish", "cs": "Czech",
            "el": "Greek", "he": "Hebrew", "th": "Thai", "vi": "Vietnamese",
            "id": "Indonesian", "ms": "Malay", "ro": "Romanian", "hu": "Hungarian",
            "uk": "Ukrainian", "ca": "Catalan", "tl": "Tagalog", "bn": "Bengali",
            "ta": "Tamil", "te": "Telugu", "ur": "Urdu", "fa": "Persian",
            "hr": "Croatian", "sk": "Slovak", "sl": "Slovenian", "sr": "Serbian",
            "bg": "Bulgarian", "lt": "Lithuanian", "lv": "Latvian", "et": "Estonian",
            "be": "Belarusian", "bs": "Bosnian", "mk": "Macedonian", "mr": "Marathi",
            "ne": "Nepali", "gu": "Gujarati", "kn": "Kannada", "pa": "Punjabi",
        }
        tts_by_lang = {}
        for v in tts_voices:
            parts = v["id"].rsplit("-", 1)
            lang_code = parts[-1] if len(parts) > 1 else "en"
            lang_entry = {"code": lang_code, "name": lang_names.get(lang_code, lang_code.upper())}
            if lang_code not in tts_by_lang:
                tts_by_lang[lang_code] = {"language": lang_entry, "voices": []}
            tts_by_lang[lang_code]["voices"].append(v)

        # Collect available languages — union of TTS + STT supported languages
        # TTS languages (from voice names)
        tts_lang_codes = set(tts_by_lang.keys())
        # STT languages from Nova-3 (all languages Deepgram STT supports)
        nova3_langs = [
            "ar", "be", "bn", "bs", "bg", "ca", "zh", "hr", "cs", "da", "nl",
            "en", "et", "fi", "fr", "de", "el", "gu", "he", "hi", "hu", "id",
            "it", "ja", "kn", "ko", "lv", "lt", "mk", "ms", "mr", "ne", "no",
            "fa", "pl", "pt", "ro", "ru", "sr", "sk", "sl", "es", "sv", "tl",
            "ta", "te", "th", "tr", "uk", "ur", "vi",
        ]
        all_lang_codes = sorted(tts_lang_codes | set(nova3_langs))
        available_langs = [{"code": c, "name": lang_names.get(c, c.upper())} for c in all_lang_codes]

        # STT models with language support metadata (from Deepgram docs)
        # Nova-3: all languages. Nova-2: many. Nova-1: en, es, hi. Enhanced: subset. English-only models listed separately.
        stt_all = [
            {"id": "nova-3", "name": "Nova 3 (Latest)"},
            {"id": "flux-general-en", "name": "Flux (English)"},
            {"id": "flux-general-multi", "name": "Flux (Multilingual)"},
            {"id": "nova-2", "name": "Nova 2"},
            {"id": "nova", "name": "Nova"},
            {"id": "nova-2-meeting", "name": "Nova 2 Meeting"},
            {"id": "nova-2-phonecall", "name": "Nova 2 Phonecall"},
            {"id": "nova-2-video", "name": "Nova 2 Video"},
            {"id": "nova-2-medical", "name": "Nova 2 Medical"},
            {"id": "nova-2-finance", "name": "Nova 2 Finance"},
            {"id": "base", "name": "Base"},
            {"id": "enhanced", "name": "Enhanced"},
        ]
        # Models that support all languages
        stt_nova3_models = {"nova-3", "flux-general-multi"}
        # Models that support many (but not all) languages
        stt_nova2_langs = {"bg","ca","zh","cs","da","nl","en","et","fi","fr","de","el","hi","hu","id","it","ja","ko","lv","lt","ms","no","pl","pt","ro","ru","sk","es","sv","th","tr","uk","vi"}
        stt_nova1_langs = {"en", "es", "hi"}
        stt_enhanced_langs = {"da","nl","en","fr","de","hi","it","ja","ko","no","pl","pt","es","sv","ta"}
        stt_english_only = {"nova-2-meeting", "nova-2-phonecall", "nova-2-video", "nova-2-medical", "nova-2-finance", "flux-general-en"}

        stt_by_lang = {}
        for lang in available_langs:
            code = lang["code"]
            models_for_lang = []
            for m in stt_all:
                mid = m["id"]
                if mid in stt_nova3_models:
                    models_for_lang.append(m)
                elif mid == "nova-2" and code in stt_nova2_langs:
                    models_for_lang.append(m)
                elif mid == "nova" and code in stt_nova1_langs:
                    models_for_lang.append(m)
                elif mid == "base" and code in stt_nova2_langs:
                    models_for_lang.append(m)
                elif mid == "enhanced" and code in stt_enhanced_langs:
                    models_for_lang.append(m)
                elif mid in stt_english_only and code == "en":
                    models_for_lang.append(m)
            stt_by_lang[code] = {"language": lang, "models": models_for_lang}

        return {
            "stt": stt_all,
            "stt_by_language": stt_by_lang,
            "tts": tts_voices,
            "tts_by_language": tts_by_lang,
            "languages": available_langs,
        }
    elif provider_type == "elevenlabs":
        tts_voices = [
            {"id": "eleven_multilingual_v2", "name": "Multilingual v2"},
            {"id": "eleven_turbo_v2", "name": "Turbo v2"},
            {"id": "eleven_turbo_v2_5", "name": "Turbo v2.5"},
            {"id": "eleven_flash_v2_5", "name": "Flash v2.5"},
            {"id": "eleven_monolingual_v1", "name": "Monolingual v1"},
        ]
        # ElevenLabs models are language-agnostic; language is set via API param
        eleven_langs = [
            {"code": "en", "name": "English"}, {"code": "es", "name": "Spanish"},
            {"code": "fr", "name": "French"}, {"code": "de", "name": "German"},
            {"code": "it", "name": "Italian"}, {"code": "pt", "name": "Portuguese"},
            {"code": "pl", "name": "Polish"}, {"code": "nl", "name": "Dutch"},
            {"code": "tr", "name": "Turkish"}, {"code": "sv", "name": "Swedish"},
            {"code": "ja", "name": "Japanese"}, {"code": "ko", "name": "Korean"},
            {"code": "zh", "name": "Chinese"}, {"code": "ar", "name": "Arabic"},
            {"code": "hi", "name": "Hindi"}, {"code": "ru", "name": "Russian"},
        ]
        # All ElevenLabs models are available for all languages
        tts_by_lang = {}
        stt_by_lang = {}
        stt_all = [{"id": "scribe_v1", "name": "Scribe v1"}, {"id": "scribe_v1_base", "name": "Scribe v1 Base"}]
        for lang in eleven_langs:
            tts_by_lang[lang["code"]] = {"language": lang, "voices": tts_voices}
            stt_by_lang[lang["code"]] = {"language": lang, "models": stt_all}
        return {
            "stt": stt_all,
            "stt_by_language": stt_by_lang,
            "tts": tts_voices,
            "tts_by_language": tts_by_lang,
            "languages": eleven_langs,
        }
    return {"stt": [], "tts": [], "languages": [], "tts_by_language": {}}
