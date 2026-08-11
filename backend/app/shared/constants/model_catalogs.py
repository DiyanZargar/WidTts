"""Centralized provider model catalogs.

Single source of truth for all speech provider models, voices, and languages.
Routes import from here instead of maintaining their own copies.
"""


# ── Flux → Aura Model Mapping ──────────────────────────────────────

FLUX_TO_AURA_MAP = {
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

# ── Deepgram Fallback Models ────────────────────────────────────────

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
    {"id": "flux-rufus-en", "name": "Flux Rufus (Conversational Male)"},
    {"id": "flux-asteria-en", "name": "Flux Asteria (Conversational Female)"},
    {"id": "flux-stella-en", "name": "Flux Stella (Conversational Female)"},
    {"id": "flux-luna-en", "name": "Flux Luna (Conversational Female)"},
    {"id": "flux-arcas-en", "name": "Flux Arcas (Conversational Male)"},
    {"id": "flux-orion-en", "name": "Flux Orion (Conversational Male)"},
    {"id": "flux-zeus-en", "name": "Flux Zeus (Conversational Male)"},
    {"id": "aura-asteria-en", "name": "Aura Asteria (US Female)"},
    {"id": "aura-luna-en", "name": "Aura Luna (US Female)"},
    {"id": "aura-stella-en", "name": "Aura Stella (US Female)"},
    {"id": "aura-athena-en", "name": "Aura Athena (UK Female)"},
    {"id": "aura-hera-en", "name": "Aura Hera (US Female)"},
    {"id": "aura-orion-en", "name": "Aura Orion (US Male)"},
    {"id": "aura-arcas-en", "name": "Aura Arcas (US Male)"},
    {"id": "aura-perseus-en", "name": "Aura Perseus (US Male)"},
    {"id": "aura-angus-en", "name": "Aura Angus (UK Male)"},
    {"id": "aura-orpheus-en", "name": "Aura Orpheus (US Male)"},
    {"id": "aura-helios-en", "name": "Aura Helios (UK Male)"},
    {"id": "aura-zeus-en", "name": "Aura Zeus (US Male)"},
]

# ── ElevenLabs Fallback Models ──────────────────────────────────────

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

# ── Fish Audio TTS Models ───────────────────────────────────────────

FISH_AUDIO_TTS_MODELS = [
    {"id": "s2.1-pro", "name": "S2.1 Pro (83 Languages, Recommended)"},
    {"id": "s2.1-pro-free", "name": "S2.1 Pro Free (83 Languages)"},
    {"id": "s2-pro", "name": "S2 Pro (80+ Languages)"},
    {"id": "s1", "name": "S1 (13 Languages)"},
]


def get_speech_models(provider_type: str) -> dict:
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

        # Languages verified from official docs:
        # Deepgram Nova-3 STT: 50+ languages
        # Deepgram Aura-2 TTS: en, es, nl, fr, de, it, ja (7 languages)
        # ElevenLabs TTS v2: 29 languages. Flash v2.5: 32 languages (adds hu, no, vi)
        # ElevenLabs STT (Scribe): supports same language set as their TTS
        # Only languages verified from both providers' official documentation
        lang_names = {
            "en": "English", "es": "Spanish", "fr": "French", "de": "German",
            "hi": "Hindi", "ja": "Japanese", "zh": "Chinese", "ko": "Korean",
            "pt": "Portuguese", "it": "Italian", "id": "Indonesian", "nl": "Dutch",
            "tr": "Turkish", "tl": "Filipino", "pl": "Polish", "sv": "Swedish",
            "bg": "Bulgarian", "ro": "Romanian", "ar": "Arabic", "cs": "Czech",
            "el": "Greek", "fi": "Finnish", "hr": "Croatian", "ms": "Malay",
            "sk": "Slovak", "da": "Danish", "ta": "Tamil", "uk": "Ukrainian",
            "ru": "Russian", "hu": "Hungarian", "no": "Norwegian", "vi": "Vietnamese",
            # Deepgram STT only (no ElevenLabs TTS/STT support)
            "be": "Belarusian", "bn": "Bengali", "bs": "Bosnian", "ca": "Catalan",
            "et": "Estonian", "gu": "Gujarati", "he": "Hebrew", "kn": "Kannada",
            "lt": "Lithuanian", "lv": "Latvian", "mk": "Macedonian", "mr": "Marathi",
            "ne": "Nepali", "fa": "Persian", "pa": "Punjabi", "sl": "Slovenian",
            "sr": "Serbian", "te": "Telugu", "th": "Thai", "ur": "Urdu",
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
            {"id": "eleven_v3", "name": "Eleven v3 (Latest)"},
            {"id": "eleven_multilingual_v2", "name": "Multilingual v2"},
            {"id": "eleven_flash_v2_5", "name": "Flash v2.5 (Low Latency)"},
            {"id": "eleven_turbo_v2_5", "name": "Turbo v2.5"},
            {"id": "eleven_turbo_v2", "name": "Turbo v2"},
            {"id": "eleven_monolingual_v1", "name": "Monolingual v1 (English)"},
        ]
        # ElevenLabs models are language-agnostic; language is set via API param
        # ElevenLabs: 32 languages verified from official docs (Flash v2.5)
        # Multilingual v2: 29 languages. Flash v2.5: +hu, +no, +vi = 32
        eleven_langs = [
            {"code": "en", "name": "English"}, {"code": "ja", "name": "Japanese"},
            {"code": "zh", "name": "Chinese"}, {"code": "de", "name": "German"},
            {"code": "hi", "name": "Hindi"}, {"code": "fr", "name": "French"},
            {"code": "ko", "name": "Korean"}, {"code": "pt", "name": "Portuguese"},
            {"code": "it", "name": "Italian"}, {"code": "es", "name": "Spanish"},
            {"code": "id", "name": "Indonesian"}, {"code": "nl", "name": "Dutch"},
            {"code": "tr", "name": "Turkish"}, {"code": "tl", "name": "Filipino"},
            {"code": "pl", "name": "Polish"}, {"code": "sv", "name": "Swedish"},
            {"code": "bg", "name": "Bulgarian"}, {"code": "ro", "name": "Romanian"},
            {"code": "ar", "name": "Arabic"}, {"code": "cs", "name": "Czech"},
            {"code": "el", "name": "Greek"}, {"code": "fi", "name": "Finnish"},
            {"code": "hr", "name": "Croatian"}, {"code": "ms", "name": "Malay"},
            {"code": "sk", "name": "Slovak"}, {"code": "da", "name": "Danish"},
            {"code": "ta", "name": "Tamil"}, {"code": "uk", "name": "Ukrainian"},
            {"code": "ru", "name": "Russian"},
            # Flash v2.5 adds these 3:
            {"code": "hu", "name": "Hungarian"},
            {"code": "no", "name": "Norwegian"},
            {"code": "vi", "name": "Vietnamese"},
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
    elif provider_type == "fishaudio":
        # TTS engine models (shown in the Model dropdown)
        tts_models = [
            {"id": "s2.1-pro", "name": "S2.1 Pro (83 Languages, Recommended)"},
            {"id": "s2.1-pro-free", "name": "S2.1 Pro Free (83 Languages)"},
            {"id": "s2-pro", "name": "S2 Pro (80+ Languages)"},
            {"id": "s1", "name": "S1 (13 Languages)"},
        ]
        # Languages supported by Fish Audio
        fish_langs = [
            {"code": "en", "name": "English"}, {"code": "es", "name": "Spanish"},
            {"code": "fr", "name": "French"}, {"code": "de", "name": "German"},
            {"code": "hi", "name": "Hindi"}, {"code": "ja", "name": "Japanese"},
            {"code": "zh", "name": "Chinese"}, {"code": "ko", "name": "Korean"},
            {"code": "pt", "name": "Portuguese"}, {"code": "it", "name": "Italian"},
            {"code": "id", "name": "Indonesian"}, {"code": "nl", "name": "Dutch"},
            {"code": "tr", "name": "Turkish"}, {"code": "tl", "name": "Filipino"},
            {"code": "pl", "name": "Polish"}, {"code": "sv", "name": "Swedish"},
            {"code": "bg", "name": "Bulgarian"}, {"code": "ro", "name": "Romanian"},
            {"code": "ar", "name": "Arabic"}, {"code": "cs", "name": "Czech"},
            {"code": "el", "name": "Greek"}, {"code": "fi", "name": "Finnish"},
            {"code": "hr", "name": "Croatian"}, {"code": "ms", "name": "Malay"},
            {"code": "sk", "name": "Slovak"}, {"code": "da", "name": "Danish"},
            {"code": "ta", "name": "Tamil"}, {"code": "uk", "name": "Ukrainian"},
            {"code": "ru", "name": "Russian"}, {"code": "hu", "name": "Hungarian"},
            {"code": "no", "name": "Norwegian"}, {"code": "vi", "name": "Vietnamese"},
            {"code": "be", "name": "Belarusian"}, {"code": "bn", "name": "Bengali"},
            {"code": "bs", "name": "Bosnian"}, {"code": "ca", "name": "Catalan"},
            {"code": "et", "name": "Estonian"}, {"code": "gu", "name": "Gujarati"},
            {"code": "he", "name": "Hebrew"}, {"code": "kn", "name": "Kannada"},
            {"code": "lt", "name": "Lithuanian"}, {"code": "lv", "name": "Latvian"},
            {"code": "mk", "name": "Macedonian"}, {"code": "mr", "name": "Marathi"},
            {"code": "ne", "name": "Nepali"}, {"code": "fa", "name": "Persian"},
            {"code": "pa", "name": "Punjabi"}, {"code": "sl", "name": "Slovenian"},
            {"code": "sr", "name": "Serbian"}, {"code": "te", "name": "Telugu"},
            {"code": "th", "name": "Thai"}, {"code": "ur", "name": "Urdu"},
            {"code": "af", "name": "Afrikaans"}, {"code": "am", "name": "Amharic"},
            {"code": "as", "name": "Assamese"}, {"code": "az", "name": "Azerbaijani"},
            {"code": "cy", "name": "Welsh"}, {"code": "eu", "name": "Basque"},
            {"code": "gl", "name": "Galician"}, {"code": "ka", "name": "Georgian"},
            {"code": "km", "name": "Khmer"}, {"code": "lo", "name": "Lao"},
            {"code": "ml", "name": "Malayalam"}, {"code": "mn", "name": "Mongolian"},
            {"code": "my", "name": "Burmese"}, {"code": "si", "name": "Sinhala"},
            {"code": "sw", "name": "Swahili"}, {"code": "uz", "name": "Uzbek"},
            {"code": "zu", "name": "Zulu"},
        ]
        # tts_by_language is empty — real voices are fetched dynamically from
        # the Fish Audio voice library API via /bots/speech-voices/{provider_id}
        return {
            "stt": [],
            "stt_by_language": {},
            "tts": tts_models,
            "tts_by_language": {},
            "languages": fish_langs,
        }
    return {"stt": [], "tts": [], "languages": [], "tts_by_language": {}, "stt_by_language": {}}

