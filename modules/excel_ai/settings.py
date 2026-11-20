"""Runtime settings for Excel AI.

All values can be overridden without editing source code.
Uses BahonIQ Cloud AI (Google Gemini Flash).
"""

from __future__ import annotations

import os

REQUEST_TIMEOUT = int(os.getenv("BAHONIQ_AI_TIMEOUT", "45"))
CONTEXT_SIZE = int(os.getenv("BAHONIQ_AI_CONTEXT", "16384"))
MAX_ANALYSIS_CHARS = int(os.getenv("BAHONIQ_AI_ANALYSIS_CHARS", "32000"))
