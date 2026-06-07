"""
edge_tts_func.py — Microsoft Edge TTS (free, no API key, online).

Works on Python 3.13+. Returns MP3 audio.
Install: pip install edge-tts

Voices: https://speech.microsoft.com/portal/voicegallery
Good anime-friendly female voices:
  en-US-AriaNeural     — natural, warm, clear (default)
  en-US-JennyNeural    — slightly softer
  en-GB-SoniaNeural    — British accent
"""

import asyncio
from pathlib import Path


VOICE = "en-US-AriaNeural"


def edge_gen(text: str, output_path: str | Path, voice: str | None = None) -> Path | None:
    """Synthesise speech with edge-tts. Returns path to .mp3 or None on failure."""
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        print("[Edge TTS] Not installed — run: pip install edge-tts")
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    selected_voice = voice or VOICE

    async def _generate():
        import edge_tts as _edge
        communicate = _edge.Communicate(text, selected_voice)
        await communicate.save(str(output_path))

    try:
        asyncio.run(_generate())
        return output_path if output_path.exists() and output_path.stat().st_size > 0 else None
    except Exception as e:
        print(f"[Edge TTS] Error: {e}")
        return None
