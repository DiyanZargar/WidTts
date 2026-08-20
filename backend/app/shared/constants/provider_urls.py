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
GOOGLE_OPENAI_API_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
GROQ_API_URL = "https://api.groq.com/openai/v1"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1"
TOGETHER_API_URL = "https://api.together.xyz/v1"

# Map of standard provider types to their default OpenAI-compatible base URLs
PROVIDER_DEFAULT_BASE_URLS = {
    "openai": OPENAI_API_URL,
    "groq": GROQ_API_URL,
    "openrouter": OPENROUTER_API_URL,
    "mistral": MISTRAL_API_URL,
    "moonshot": MOONSHOT_API_URL,
    "ollama": OLLAMA_API_URL,
    "deepseek": DEEPSEEK_API_URL,
    "together": TOGETHER_API_URL,
    "google": GOOGLE_OPENAI_API_URL,
}

# ── Speech Provider Base URLs ────────────────────────────────────────
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"
DEEPGRAM_API_URL = "https://api.deepgram.com"
FISH_AUDIO_API_URL = "https://api.fish.audio"
