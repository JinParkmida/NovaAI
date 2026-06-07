"""
app.py — Nova web server (tutorial version, FastAPI)

Serves the browser-based UI and handles chat API requests.

Run via main_chat.py --web, or directly:
  uvicorn app:app --port 7860
"""

import sys
import uuid
from pathlib import Path
from contextlib import asynccontextmanager

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

# ── Path setup ─────────────────────────────────────────────────────────────────

SERVER_DIR    = Path(__file__).parent.resolve()
ROOT_DIR      = SERVER_DIR.parent
CLIENT_DIR    = ROOT_DIR / "client"
CHARACTER_DIR = ROOT_DIR / "character_files"
AUDIO_DIR     = SERVER_DIR / "audio"
CONFIG_PATH   = ROOT_DIR / "character_config.yaml"
AUDIO_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(SERVER_DIR))

# ── Config helpers ─────────────────────────────────────────────────────────────

def _read_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _write_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True,
                  sort_keys=False, width=120)


def _deep_merge(base: dict, updates: dict) -> None:
    """Recursively merge updates into base in-place."""
    for key, value in updates.items():
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


# ── TTS chain ──────────────────────────────────────────────────────────────────

def _generate_audio(text: str, voice_override: str | None = None) -> str | None:
    """
    Generate TTS audio. Returns filename (relative to AUDIO_DIR) or None.
    Chain: SoVITS → edge-tts → give up.
    """
    uid = uuid.uuid4().hex[:8]

    # 1. GPT-SoVITS (best quality, needs separate server)
    try:
        from process.tts_func.sovits_ping import sovits_gen, is_sovits_running
        if is_sovits_running():
            wav_path = AUDIO_DIR / f"nova_{uid}.wav"
            if sovits_gen(text, wav_path):
                print("[TTS] SoVITS ✓")
                return f"nova_{uid}.wav"
    except Exception as e:
        print(f"[TTS] SoVITS skipped: {e}")

    # 2. Edge TTS (free, online, good quality)
    try:
        from process.tts_func.edge_tts_func import edge_gen, VOICE as DEFAULT_VOICE
        mp3_path = AUDIO_DIR / f"nova_{uid}.mp3"
        voice = voice_override or DEFAULT_VOICE
        if edge_gen(text, mp3_path, voice=voice):
            print("[TTS] Edge TTS ✓")
            return f"nova_{uid}.mp3"
    except Exception as e:
        print(f"[TTS] Edge TTS skipped: {e}")

    print("[TTS] No TTS engine available — text only")
    return None


def _cleanup_old_audio():
    import time
    now = time.time()
    for pattern in ("nova_*.mp3", "nova_*.wav"):
        for f in AUDIO_DIR.glob(pattern):
            try:
                if now - f.stat().st_mtime > 60:
                    f.unlink()
            except OSError:
                pass


# ── App ────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n[Nova] Server started. Open http://localhost:7860 in your browser.\n")
    yield
    for pattern in ("nova_*.wav", "nova_*.mp3"):
        for f in AUDIO_DIR.glob(pattern):
            f.unlink(missing_ok=True)


app = FastAPI(title="Nova", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/character_files", StaticFiles(directory=str(CHARACTER_DIR)), name="character")
app.mount("/audio",           StaticFiles(directory=str(AUDIO_DIR)),     name="audio")
if (CLIENT_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(CLIENT_DIR / "static")), name="static")


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/")
async def serve_ui():
    index = CLIENT_DIR / "index.html"
    if not index.exists():
        return JSONResponse({"error": "Client not found"}, status_code=500)
    return FileResponse(str(index))


@app.get("/api/config")
async def get_config():
    cfg = _read_config()

    _vrm_name = cfg.get("character", {}).get("vrm_model")
    if _vrm_name:
        _vrm_candidate = CHARACTER_DIR / _vrm_name
        vrm_file = _vrm_candidate if _vrm_candidate.exists() else next(
            (f for f in CHARACTER_DIR.iterdir() if f.suffix.lower() == ".vrm"), None
        )
    else:
        vrm_file = next(
            (f for f in CHARACTER_DIR.iterdir() if f.suffix.lower() == ".vrm"), None
        )

    bg_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    bg_file = next(
        (f for f in CHARACTER_DIR.iterdir()
         if f.stem.lower() == "background" and f.suffix.lower() in bg_extensions),
        None,
    )

    return {
        "character_name": cfg["character"]["name"],
        "vrm_available":  vrm_file is not None,
        "vrm_url":        f"/character_files/{vrm_file.name}" if vrm_file else None,
        "background_url": f"/character_files/{bg_file.name}"  if bg_file  else None,
        "tts_primary":    cfg.get("tts", {}).get("primary", "edge-tts"),
    }


@app.get("/api/settings")
async def get_settings():
    cfg = _read_config()
    return {
        "character": cfg.get("character", {}),
        "presets":   cfg.get("presets",   {}),
        "llm":       cfg.get("llm",       {}),
        "tts":       cfg.get("tts",       {}),
        "memory":    cfg.get("memory",    {}),
    }


@app.post("/api/settings")
async def update_settings(body: dict):
    def _save():
        cfg = _read_config()
        _deep_merge(cfg, body)
        _write_config(cfg)

    await run_in_threadpool(_save)
    return {"status": "saved"}


@app.get("/api/models")
async def get_models():
    def _fetch():
        try:
            import requests
            resp = requests.get("http://localhost:11434/api/tags", timeout=3)
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    models = await run_in_threadpool(_fetch)
    return {"models": models}


@app.post("/api/tts/test")
async def test_tts(body: dict):
    text  = body.get("text",  "Hey! This is how I sound with this voice.")
    voice = body.get("voice", "en-US-AriaNeural")
    uid   = uuid.uuid4().hex[:8]
    mp3_path = AUDIO_DIR / f"test_{uid}.mp3"

    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(mp3_path))
        if mp3_path.exists() and mp3_path.stat().st_size > 0:
            return {"audio_url": f"/audio/test_{uid}.mp3"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=500, detail="TTS generation failed")


# ── Chat ───────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Empty message")

    await run_in_threadpool(_cleanup_old_audio)

    from process.llm_funcs.llm_scr import llm_response
    reply = await run_in_threadpool(llm_response, req.message)

    audio_filename = await run_in_threadpool(_generate_audio, reply)
    audio_url = f"/audio/{audio_filename}" if audio_filename else None

    return {"text": reply, "audio_url": audio_url}


@app.delete("/api/history")
async def clear_history():
    from process.llm_funcs.llm_scr import clear_history as _clear
    await run_in_threadpool(_clear)
    return {"status": "cleared"}


# ── Dev entrypoint ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=7860, reload=True)
