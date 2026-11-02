"""Runtime settings for Excel AI.

All values can be overridden without editing source code.  The defaults are
chosen for a local Windows installation of Ollama.
"""

from __future__ import annotations

import os


OLLAMA_URL = os.getenv("BAHONIQ_OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_TAGS_URL = os.getenv("BAHONIQ_OLLAMA_TAGS_URL", "http://localhost:11434/api/tags")
PREFERRED_MODEL = os.getenv("BAHONIQ_OLLAMA_MODEL", "qwen2.5:7b")
REQUEST_TIMEOUT = int(os.getenv("BAHONIQ_AI_TIMEOUT", "300"))
CONTEXT_SIZE = int(os.getenv("BAHONIQ_AI_CONTEXT", "16384"))
MAX_ANALYSIS_CHARS = int(os.getenv("BAHONIQ_AI_ANALYSIS_CHARS", "24000"))
