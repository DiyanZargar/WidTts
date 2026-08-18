"""Centralized provider API base URLs.

Every hardcoded provider URL in the codebase should import from here
so there is a single source of truth for endpoints.
"""

# ── LLM Provider Base URLs ──────────────────────────────────────────
OPENAI_API_URL = "https://api.openai.com/v1"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1"
MISTRAL_API_URL = "https://api.mistral.ai/v1"
MOONSHOT_API_URL = "https://api.moonshot.cn/v1"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1"
OLLAMA_API_URL = "http://localhost:11434/v1"
GOOGLE_API_URL = "https://generativelanguage.googleapis.com/v1beta"

# ── Speech Provider Base URLs ────────────────────────────────────────
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"
DEEPGRAM_API_URL = "https://api.deepgram.com"
FISH_AUDIO_API_URL = "https://api.fish.audio"
