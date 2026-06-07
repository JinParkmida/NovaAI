# Build Nova: A Local AI Companion with a Live 3D Avatar

**Add a live 3D avatar, voice, and persistent memory with Ollama, FastAPI, and Three.js.**

*Jin Park · ~75 min · June 2026*

**Prerequisites:** Python fundamentals, basic HTML/JavaScript, command line comfort  
**Level:** Intermediate  
**Stack:** Ollama · FastAPI · edge-tts · Three.js · VRM

---

![Nova — Build your own local AI companion](https://raw.githubusercontent.com/JinParkmida/NovaAI/main/assets/header.png)

---

## Introduction

Most AI chat interfaces are the same box: white background, a text field, a loading spinner. There's no presence to them — nothing that makes the experience feel like more than a search engine with better grammar.

Nova is different. Nova is a local AI companion that runs the language model entirely on your own GPU — no OpenAI key, no monthly bill, no data leaving your machine. She has a 3D anime avatar that blinks, breathes, and animates her mouth when she speaks. She responds in a natural voice. She remembers your conversations.

The stack is three pieces working together:

- **Ollama** — runs a large language model locally on your GPU (or CPU)
- **FastAPI** — a Python server that handles chat, memory, and text-to-speech
- **Three.js + VRM** — renders a 3D avatar in the browser with real-time animations

By the end of this tutorial you'll have exactly that running at `http://localhost:7860`. Let's build it.

---

## What Runs Locally vs. Online?

Before we start building, here's an honest breakdown. I think it's important to be upfront about this, especially if you care about privacy:

| Component | Local or online? |
|-----------|-----------------|
| Ollama LLM (chat brain) | ✅ Fully local |
| FastAPI backend | ✅ Fully local |
| VRM avatar rendering | ✅ Fully local |
| Chat history | ✅ Stored locally as JSON |
| Three.js / VRM libraries | ⚠️ Loaded from CDN on first page load |
| Google Fonts | ⚠️ Loaded from Google on first page load |
| edge-tts voice | ⚠️ **Online** — sends text to Microsoft's neural TTS |

**The language model never sends data anywhere.** That's the part that matters. The voice is the one tradeoff — Microsoft's edge-tts is free, sounds great, and requires no sign-up, but it is online. If you need fully local voice later, I'll point you to Piper TTS in the "What's Next" section.

---

## What You'll Need

- **Python 3.10+** and `pip`
- **[Ollama](https://ollama.com/download)** installed and running
- A GPU is strongly recommended (NVIDIA with 6GB+ VRAM). CPU works but responses will be slow.
- A `.vrm` avatar file — free ones at [VRoid Hub](https://hub.vroid.com)
- An internet connection (for CDN libraries and edge-tts on first use)

---

## Step 1 — Install Ollama and Pull a Model

[Ollama](https://ollama.com/download) is a local LLM server that wraps open-source models in an OpenAI-compatible API. This is important — it means we can use the standard `openai` Python client pointed at `localhost` instead of the cloud. Install it, then pull a model:

```bash
ollama pull llama3.1:8b
```

Pick the right model for your hardware:

> **8GB VRAM (RTX 4060 etc.):** `llama3.1:8b` at Q4 uses ~4.7GB — a comfortable fit.  
> **6GB VRAM:** Try `phi4-mini` (~2.5GB) or `qwen2.5:3b` (~2GB).  
> **16GB+ VRAM:** `qwen2.5:14b` gives noticeably stronger reasoning.  
> **CPU only:** Any model works, expect 3–30 seconds per response.

Before moving on, verify Ollama responds:

```bash
ollama run llama3.1:8b "say hello in one sentence"
```

You should see a response in your terminal. **Leave Ollama running** — it stays alive in the background.

---

## Step 2 — Get a VRM Avatar

VRM is an open 3D avatar format designed for humanoid characters. Think of it as a "portable anime character" format — it bundles the mesh, materials, bones, and blend shapes (facial expressions) into one file.

1. Go to [hub.vroid.com](https://hub.vroid.com)
2. Find an avatar with a license that allows download and personal use (look for CC0 or "Available for modification")
3. Download the `.vrm` file

You can also create your own with [VRoid Studio](https://vroid.com/en/studio) — it's free and exports VRM directly, no 3D experience required. This tutorial works with any VRM 0.x or 1.x model.

---

## Step 3 — Project Structure

Create your project folder and set up this layout:

```bash
mkdir nova-ai
cd nova-ai
```

```
nova-ai/
├── character_config.yaml   ← all settings live here; re-read on every message
├── character_files/
│   └── nova.vrm            ← your VRM avatar file goes here
├── server/
│   ├── audio/              ← TTS audio files, auto-created at runtime
│   ├── data/               ← chat history JSON, auto-created at runtime
│   └── app.py              ← the FastAPI backend
└── client/
    └── index.html          ← the entire frontend (single file, no build step)
```

A few things worth noting about this layout:

`character_config.yaml` sits at the root — not inside the server — because it's something you'll edit regularly while chatting. Having it outside the server folder also means the frontend and backend can both reach it from the same relative path.

`server/audio/` and `server/data/` don't need to exist yet; the backend creates them on first run. You only need to create the folders that aren't auto-generated: `character_files/`, `server/`, and `client/`.

Move your `.vrm` file into `character_files/` now.

---

## Step 4 — Install Python Dependencies

It's good practice to isolate project dependencies in a virtual environment so they don't conflict with anything else installed on your system.

```bash
# Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

Once the environment is active, install the packages:

```bash
pip install fastapi uvicorn openai pyyaml edge-tts requests
```

Here's what each one does:

| Package | Purpose |
|---------|---------|
| `fastapi` | The web framework — handles routes, request parsing, responses |
| `uvicorn` | ASGI server that runs FastAPI |
| `openai` | The OpenAI Python client — we'll point it at Ollama instead of the cloud |
| `pyyaml` | Reads `character_config.yaml` |
| `edge-tts` | Microsoft's Neural TTS, free and requires no API key |
| `requests` | Standard HTTP client, used for a few utility calls |

`openai` might look unexpected here — we're not using OpenAI's servers at all. But Ollama deliberately exposes an OpenAI-compatible REST API at `http://localhost:11434/v1`. That means the official Python client works unchanged; we just point it at `localhost`. This is a deliberate design decision in Ollama that makes migration between local and cloud models trivial.

---

## Step 5 — Character Config

Create `character_config.yaml` at the root of your project. One file controls everything — LLM settings, voice, personality, memory window. The backend re-reads it on **every single message**, which means you can change Nova's personality mid-conversation without touching the server.

```yaml
# character_config.yaml

llm:
  provider: ollama
  base_url: http://localhost:11434/v1
  api_key: ollama          # Ollama ignores this — any string works
  model: llama3.1:8b
  temperature: 0.85        # 0 = focused/deterministic, 2 = very creative
  max_tokens: 1024

tts:
  voice: en-US-AriaNeural  # free edge-tts voice (online, no sign-up)

memory:
  history_file: ./server/data/chat_history.json
  max_history_messages: 40  # how many past messages to include in context

character:
  name: Nova
  preset: default

presets:
  default:
    system_prompt: |
      You are Nova, a helpful and witty AI companion.
      You are warm but sharp — genuine, curious, and caring.
      Keep responses concise unless the task needs detail.
```

The preset system lets you define multiple personalities and switch between them. For now, `default` is all we need.

---

## Step 6 — The FastAPI Backend

Create `server/app.py`. We'll build it in four logical sections so each piece is understandable on its own.

### 6a — Imports and paths

Start by importing everything the server needs and establishing all file paths at the module level. Setting paths once at the top — rather than building them inline throughout the code — means there's one place to look if anything ever needs to change.

```python
# server/app.py

import asyncio, uuid, yaml, json
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from openai import OpenAI

SERVER_DIR    = Path(__file__).parent.resolve()  # .../nova-ai/server/
ROOT_DIR      = SERVER_DIR.parent                # .../nova-ai/
CLIENT_DIR    = ROOT_DIR / "client"
CHARACTER_DIR = ROOT_DIR / "character_files"
AUDIO_DIR     = SERVER_DIR / "audio"
CONFIG_PATH   = ROOT_DIR / "character_config.yaml"

AUDIO_DIR.mkdir(exist_ok=True)  # create server/audio/ if it doesn't exist yet
```

All paths derive from `__file__` (the location of `app.py` itself), so the server works correctly from any working directory — no fragile relative paths that break if you run it from the wrong folder.

### 6b — Config, LLM client, and chat history

This is the core of the backend. The key design decision here is **hot-reloading**: we re-read the config on every message. This is slightly less efficient than caching it once, but it makes the system feel alive — change the personality, send a message, see the change. No restart loop.

```python
def _read_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# Cache the OpenAI client — only recreate if the base_url changes
_client_cache: dict = {"base_url": None, "client": None}

def _get_client(llm_cfg: dict) -> OpenAI:
    url = llm_cfg["base_url"]
    if _client_cache["base_url"] != url:
        _client_cache.update(
            base_url=url,
            client=OpenAI(base_url=url, api_key=llm_cfg.get("api_key", "ollama"))
        )
    return _client_cache["client"]

def llm_respond(user_input: str) -> str:
    """Hot-reloads config, sends the message to Ollama, saves history."""
    cfg     = _read_config()
    llm_cfg = cfg["llm"]
    client  = _get_client(llm_cfg)

    # Load chat history (creates the file automatically if it doesn't exist)
    history_path = ROOT_DIR / cfg["memory"]["history_file"]
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history = json.loads(history_path.read_text()) if history_path.exists() else []

    # Build messages: system prompt + recent history + new user message
    preset_name   = cfg["character"].get("preset", "default")
    system_prompt = cfg["presets"][preset_name]["system_prompt"].strip()

    messages = [{"role": "system", "content": system_prompt}]
    messages += history[-cfg["memory"]["max_history_messages"]:]
    messages.append({"role": "user", "content": user_input})

    response = client.chat.completions.create(
        model       = llm_cfg["model"],
        messages    = messages,
        temperature = llm_cfg.get("temperature", 0.85),
        max_tokens  = llm_cfg.get("max_tokens", 1024),
    )
    reply = response.choices[0].message.content or ""

    # Append both turns to history and save
    history.append({"role": "user",      "content": user_input})
    history.append({"role": "assistant", "content": reply})
    history_path.write_text(json.dumps(history, indent=2, ensure_ascii=False))

    return reply
```

### 6c — Text-to-speech

edge-tts is an async library under the hood, which creates a problem: FastAPI already has an async event loop running, and `asyncio.run()` can't nest inside one. The fix is `run_in_threadpool` — it runs the blocking `asyncio.run()` call in a separate thread where it can safely create its own event loop.

```python
def _generate_audio(text: str) -> str | None:
    """
    Synthesises speech and returns the audio filename, or None on failure.
    Note: edge-tts sends text to Microsoft's servers to generate the audio.
    """
    cfg   = _read_config()
    voice = cfg.get("tts", {}).get("voice", "en-US-AriaNeural")
    uid   = uuid.uuid4().hex[:8]
    path  = AUDIO_DIR / f"nova_{uid}.mp3"

    async def _run():
        import edge_tts
        await edge_tts.Communicate(text, voice).save(str(path))

    try:
        asyncio.run(_run())
        return f"nova_{uid}.mp3" if path.stat().st_size > 0 else None
    except Exception as e:
        print(f"[TTS] Error: {e}")
        return None
```

> **Audio cleanup:** Each TTS response writes a short `.mp3` to `server/audio/`. We delete them all on server shutdown via the `lifespan` hook below, so the folder never accumulates.

> **Changing the voice:** Update `tts.voice` in `character_config.yaml`. Browse all voices at [speech.microsoft.com/portal/voicegallery](https://speech.microsoft.com/portal/voicegallery). Good picks: `en-US-JennyNeural` (soft), `en-GB-SoniaNeural` (British), `ja-JP-NanamiNeural` (Japanese).

### 6d — FastAPI routes

Now we wire it all together. There are four things happening here worth understanding before reading the code:

- **`lifespan`** — FastAPI's startup/shutdown hook. We print the server URL on startup, and on shutdown we delete all the `.mp3` files that accumulated in `server/audio/` during the session.
- **`CORSMiddleware`** — allows the browser to make API requests to our server from any origin. Without this, the browser blocks the request with a CORS error.
- **`app.mount`** — serves static files (the VRM model, audio files) directly from the filesystem under a URL path. This is how the frontend loads the avatar and plays audio without needing extra routes.
- **`run_in_threadpool`** — since `llm_respond` and `_generate_audio` are blocking (synchronous) functions, we run them in a thread pool so they don't block FastAPI's async event loop. This keeps the server responsive.

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n[Nova] Server started → http://localhost:7860\n")
    yield  # server runs here
    # Shutdown: clean up audio files accumulated during the session
    for f in AUDIO_DIR.glob("nova_*.mp3"):
        f.unlink(missing_ok=True)

app = FastAPI(title="Nova", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

# Serve the VRM file and audio files as static assets
app.mount("/character_files", StaticFiles(directory=str(CHARACTER_DIR)), name="character")
app.mount("/audio",           StaticFiles(directory=str(AUDIO_DIR)),     name="audio")

# GET / — serve the frontend
@app.get("/")
async def serve_ui():
    return FileResponse(str(CLIENT_DIR / "index.html"))

# GET /api/config — tell the frontend what avatar to load and what to call Nova
@app.get("/api/config")
async def get_config():
    cfg = _read_config()
    vrm = next((f for f in CHARACTER_DIR.iterdir() if f.suffix == ".vrm"), None)
    return {
        "character_name": cfg["character"]["name"],
        "vrm_available":  vrm is not None,
        "vrm_url":        f"/character_files/{vrm.name}" if vrm else None,
    }

# POST /api/chat — the main route: receive a message, return a reply + audio URL
class ChatRequest(BaseModel):
    message: str

@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(400, "Empty message")
    reply    = await run_in_threadpool(llm_respond, req.message)
    audio_fn = await run_in_threadpool(_generate_audio, reply)
    return {
        "text":      reply,
        "audio_url": f"/audio/{audio_fn}" if audio_fn else None,
    }

# DELETE /api/history — wipe the chat history (used by the "clear chat" button)
@app.delete("/api/history")
async def clear_history():
    cfg  = _read_config()
    path = ROOT_DIR / cfg["memory"]["history_file"]
    if path.exists():
        path.unlink()
    return {"status": "cleared"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=7860, reload=True)
```

**Test the backend before touching the frontend.** Open two terminals:

```bash
# Terminal 1 — start the server
cd server
python app.py

# Terminal 2 — test it
curl http://localhost:7860/api/config

curl -X POST http://localhost:7860/api/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "say hello in one sentence"}'
```

If you get back JSON with a `"text"` field, the LLM is connected. If you also get `"audio_url"`, TTS is working. Don't move forward until this is solid.

---

## Step 7 — The Frontend

Create `client/index.html`. The entire frontend is a single HTML file — no npm, no build step, no `node_modules` folder of 40,000 files. We load Three.js and the VRM plugin as native ES modules via an **import map** — a browser feature that lets you write clean import paths without a bundler.

> **Why all five `@pixiv/three-vrm-*` entries?** The VRM loader is split into sub-packages. If any one of them is missing from the import map, you get a runtime import error. All five are required even if you never reference them directly.

### 7a — HTML structure and styles

The page is split into two columns using CSS grid: the left column is a fixed 400px chat panel; the right column fills the remaining space and holds the 3D avatar, rendered inside a portrait-ratio container that gives it a webcam-style look. The avatar is rendered on a `<canvas>` element that Three.js takes over — everything else in the right pane (lighting, camera, VRM model) is handled in JavaScript.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Nova</title>
  <link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700&display=swap" rel="stylesheet" />

  <script type="importmap">
  {
    "imports": {
      "three":                            "https://cdn.jsdelivr.net/npm/three@0.163.0/build/three.module.js",
      "three/addons/":                    "https://cdn.jsdelivr.net/npm/three@0.163.0/examples/jsm/",
      "@pixiv/three-vrm":                 "https://cdn.jsdelivr.net/npm/@pixiv/three-vrm@2.1.2/lib/three-vrm.module.js",
      "@pixiv/three-vrm-core":            "https://cdn.jsdelivr.net/npm/@pixiv/three-vrm-core@2.1.2/lib/three-vrm-core.module.js",
      "@pixiv/three-vrm-materials-mtoon": "https://cdn.jsdelivr.net/npm/@pixiv/three-vrm-materials-mtoon@2.1.2/lib/three-vrm-materials-mtoon.module.js",
      "@pixiv/three-vrm-node-constraint": "https://cdn.jsdelivr.net/npm/@pixiv/three-vrm-node-constraint@2.1.2/lib/three-vrm-node-constraint.module.js",
      "@pixiv/three-vrm-springbone":      "https://cdn.jsdelivr.net/npm/@pixiv/three-vrm-springbone@2.1.2/lib/three-vrm-springbone.module.js"
    }
  }
  </script>

  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #07071a; color: #e8e8f0; font-family: 'Nunito', sans-serif; height: 100vh; overflow: hidden; }
    #app { display: grid; grid-template-columns: 400px 1fr; height: 100vh; }

    /* Chat pane */
    #chat-pane {
      display: flex; flex-direction: column;
      background: #0e0e2a;
      border-right: 1px solid rgba(255,255,255,0.08);
    }

    /* Avatar pane */
    #avatar-pane {
      background: radial-gradient(ellipse at 50% 80%, #1a1040 0%, #07071a 70%);
      display: flex; align-items: center; justify-content: center;
      position: relative;
    }
    #vrm-canvas { width: 100% !important; height: 100% !important; display: block; }
    #chat-header {
      padding: 16px 20px;
      border-bottom: 1px solid rgba(255,255,255,0.08);
      display: flex; align-items: center; gap: 12px;
      font-weight: 700;
    }
    #chat-messages {
      flex: 1; overflow-y: auto;
      padding: 16px;
      display: flex; flex-direction: column; gap: 10px;
    }
    .msg { max-width: 85%; display: flex; flex-direction: column; gap: 3px; }
    .msg.user { align-self: flex-end; }
    .msg.nova  { align-self: flex-start; }
    .msg-bubble {
      padding: 9px 13px; border-radius: 14px;
      font-size: 0.88rem; line-height: 1.5; white-space: pre-wrap;
    }
    .msg.user .msg-bubble { background: #1e1b4b; border: 1px solid rgba(108,99,255,0.3); }
    .msg.nova .msg-bubble  { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); }
    .msg-label { font-size: 0.7rem; color: #7070a0; padding: 0 3px; }

    #chat-input-area {
      padding: 14px; border-top: 1px solid rgba(255,255,255,0.08);
      display: flex; gap: 8px; align-items: flex-end;
    }
    #chat-input {
      flex: 1; background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.1); border-radius: 10px;
      padding: 9px 13px; color: #e8e8f0;
      font-family: 'Nunito', sans-serif; font-size: 0.88rem;
      resize: none; outline: none; max-height: 100px;
    }
    #send-btn {
      width: 40px; height: 40px; border-radius: 10px;
      background: #6c63ff; border: none; color: white;
      cursor: pointer; font-size: 1rem; flex-shrink: 0;
    }
    #send-btn:hover    { background: #7c75ff; }
    #send-btn:disabled { background: #3a3a5c; cursor: not-allowed; }
  </style>
</head>
<body>

<div id="app">
  <div id="chat-pane">
    <div id="chat-header">
      <span>🌸</span>
      <span id="header-name">Nova</span>
    </div>
    <div id="chat-messages">
      <div class="msg nova">
        <div class="msg-label">Nova</div>
        <div class="msg-bubble">Hey! 👋 Ask me anything.</div>
      </div>
    </div>
    <div id="chat-input-area">
      <textarea id="chat-input" placeholder="Type a message…" rows="1"></textarea>
      <button id="send-btn">➤</button>
    </div>
  </div>

  <div id="avatar-pane">
    <canvas id="vrm-canvas"></canvas>
  </div>
</div>
```

### 7b — Three.js scene setup

Add this inside a `<script type="module">` tag at the bottom of the file, just before `</body>`. The `module` type is required for ES import syntax — without it, `import * as THREE` is a syntax error.

```html
<script type="module">
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

// State
let vrm       = null;
let isTalking = false;
const clock   = new THREE.Clock();

// Renderer — alpha: true gives us a transparent background so the CSS gradient shows
const canvas   = document.getElementById('vrm-canvas');
const pane     = document.getElementById('avatar-pane');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setClearColor(0x000000, 0);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping      = THREE.ACESFilmicToneMapping;

// Scene and camera
const scene  = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 10);
camera.position.set(0, 1.45, 1.5);  // eye-level portrait framing
camera.lookAt(0, 1.25, 0);

// Lighting — key light from the front-right, coloured rim from the back-left
scene.add(new THREE.AmbientLight(0xffffff, 0.6));
const key = new THREE.DirectionalLight(0xffffff, 1.2);
key.position.set(1, 2, 2);
scene.add(key);
const rim = new THREE.DirectionalLight(0x6c63ff, 0.4);
rim.position.set(-2, 1, -1);
scene.add(rim);

// Resize handler — keeps canvas filling the pane without stretching
function resize() {
  renderer.setSize(pane.clientWidth, pane.clientHeight, false);
  camera.aspect = pane.clientWidth / pane.clientHeight;
  camera.updateProjectionMatrix();
}
resize();
new ResizeObserver(resize).observe(pane);
```

### 7c — Avatar loading and idle animations

Continue inside the same `<script type="module">`:

```javascript
// ── Idle pose ────────────────────────────────────────────────────────────────

function applyIdlePose(model) {
  const h = model.humanoid;
  if (!h) return;
  const deg = THREE.MathUtils.degToRad;
  const lu = h.getNormalizedBoneNode('leftUpperArm');
  const ru = h.getNormalizedBoneNode('rightUpperArm');
  if (lu) lu.rotation.z = deg(75);    // +Z rotates leftUpperArm DOWN from T-pose
  if (ru) ru.rotation.z = deg(-75);   // -Z rotates rightUpperArm DOWN from T-pose
  model.update(0);  // ← flush bone transforms immediately (see callout below)
}

// ── Animation loop ────────────────────────────────────────────────────────────

let breathT = 0, blinkTimer = 3, blinkT = 0, blinkPhase = 'idle';

function animate() {
  requestAnimationFrame(animate);
  const dt = clock.getDelta();

  if (vrm) {
    // Subtle breathing bob — a slow sine wave on the Y position
    breathT += dt * 0.6;
    vrm.scene.position.y = Math.sin(breathT) * 0.003;

    // Natural blinking — three-phase: closing (70ms), closed (50ms), opening (100ms)
    blinkTimer -= dt;
    if (blinkPhase === 'idle' && blinkTimer <= 0) {
      blinkPhase = 'closing'; blinkT = 0;
    }
    if (blinkPhase === 'closing') {
      blinkT += dt / 0.07;
      vrm.expressionManager?.setValue('blink', Math.min(blinkT, 1));
      if (blinkT >= 1) { blinkPhase = 'closed'; blinkT = 0; }
    } else if (blinkPhase === 'closed') {
      blinkT += dt;
      if (blinkT >= 0.05) { blinkPhase = 'opening'; blinkT = 0; }
    } else if (blinkPhase === 'opening') {
      blinkT += dt / 0.1;
      vrm.expressionManager?.setValue('blink', 1 - Math.min(blinkT, 1));
      if (blinkT >= 1) {
        vrm.expressionManager?.setValue('blink', 0);
        blinkPhase = 'idle';
        blinkTimer = 3 + Math.random() * 4;  // next blink in 3–7 seconds
      }
    }

    // Mouth — drives the 'aa' (open mouth) blend shape while audio is playing
    if (isTalking) {
      vrm.expressionManager?.setValue('aa',
        (Math.sin(Date.now() / 125) * 0.5 + 0.5) * 0.7
      );
    } else {
      // Smooth decay back to closed when speech ends
      const cur = vrm.expressionManager?.getValue?.('aa') ?? 0;
      vrm.expressionManager?.setValue('aa', cur > 0.01 ? cur * 0.85 : 0);
    }

    vrm.update(dt);  // update springbone physics (hair, clothing movement)
  }

  renderer.render(scene, camera);
}

animate();

// ── VRM loading ───────────────────────────────────────────────────────────────

async function loadVRM(url) {
  const loader = new GLTFLoader();
  loader.register(parser => new VRMLoaderPlugin(parser));

  return new Promise((resolve, reject) => {
    loader.load(url, (gltf) => {
      const model = gltf.userData.vrm;
      if (!model) { reject(new Error('No VRM data found in file')); return; }

      VRMUtils.removeUnnecessaryVertices(gltf.scene);
      VRMUtils.removeUnnecessaryJoints(gltf.scene);

      // VRM 0.x models face -Z; VRM 1.x face +Z. Detect and fix accordingly.
      const exts   = gltf.parser.json.extensions || {};
      const isVRM0 = 'VRM' in exts && !('VRMC_vrm' in exts);
      if (isVRM0) VRMUtils.rotateVRM0(model);

      scene.add(model.scene);
      applyIdlePose(model);
      resolve(model);
    }, undefined, reject);
  });
}
```

> **Why `model.update(0)` in `applyIdlePose`?** When you set bone rotations, the VRM spring-bone system needs one tick to propagate those transforms through the skeleton. Without this call, the avatar flashes in the default T-pose on the very first frame before the animation loop picks up. `update(0)` forces that propagation immediately with zero elapsed time.

> **Why `rotateVRM0`?** VRM 0.x (the version most VRoid Hub exports use) stores avatars facing the -Z direction, while Three.js cameras point in -Z. The result: the avatar faces away from you. `rotateVRM0` applies a 180° Y-axis rotation to fix it. We detect the version by checking GLTF extension keys: `'VRM'` present without `'VRMC_vrm'` means 0.x.

### 7d — Chat and audio

Still inside the same `<script type="module">`, add the remaining JavaScript. This section covers three things: `init()` fetches the config from the server and loads the VRM model; `addMessage()` creates a message bubble in the chat panel; and `sendMessage()` posts the user's input to `/api/chat`, displays the reply, and plays the audio — which is also what drives the mouth animation via the `isTalking` flag we set up in the animation loop.

```javascript
// ── App init ─────────────────────────────────────────────────────────────────

async function init() {
  const res    = await fetch('/api/config');
  const config = await res.json();
  document.getElementById('header-name').textContent = config.character_name;
  document.title = config.character_name;
  if (config.vrm_available) {
    vrm = await loadVRM(config.vrm_url);
  }
}
init().catch(console.error);

// ── Chat UI ───────────────────────────────────────────────────────────────────

const messagesEl = document.getElementById('chat-messages');
const inputEl    = document.getElementById('chat-input');
const sendBtn    = document.getElementById('send-btn');

function addMessage(role, text) {
  const wrap   = document.createElement('div');
  wrap.className = `msg ${role}`;
  const label  = document.createElement('div');
  label.className   = 'msg-label';
  label.textContent = role === 'user'
    ? 'You'
    : document.getElementById('header-name').textContent;
  const bubble = document.createElement('div');
  bubble.className   = 'msg-bubble';
  bubble.textContent = text;
  wrap.append(label, bubble);
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function sendMessage() {
  const text = inputEl.value.trim();
  if (!text) return;

  addMessage('user', text);
  inputEl.value    = '';
  sendBtn.disabled = true;

  try {
    const res  = await fetch('/api/chat', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ message: text }),
    });
    if (!res.ok) throw new Error(`Server returned ${res.status}`);
    const data = await res.json();
    addMessage('nova', data.text);

    // If TTS audio came back, play it and drive the mouth animation
    if (data.audio_url) {
      const audio = new Audio(data.audio_url);
      isTalking   = true;
      audio.addEventListener('ended', () => { isTalking = false; });
      audio.addEventListener('error', () => { isTalking = false; });
      audio.play().catch(() => { isTalking = false; });
    }
  } catch (err) {
    addMessage('nova', `[Error: ${err.message}]`);
  } finally {
    sendBtn.disabled = false;
    inputEl.focus();
  }
}

sendBtn.addEventListener('click', sendMessage);
inputEl.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
// Auto-resize the textarea as the user types
inputEl.addEventListener('input', () => {
  inputEl.style.height = '';
  inputEl.style.height = Math.min(inputEl.scrollHeight, 100) + 'px';
});
</script>
</body>
</html>
```

---

## Step 8 — Run It

```bash
cd server
python app.py
```

Open **http://localhost:7860** in your browser.

![Nova loaded — chat panel on the left, avatar in webcam-style container on the right](https://raw.githubusercontent.com/JinParkmida/NovaAI/main/assets/sc1.png)

Here's what you should see:

1. The 3D avatar loads and stands naturally — arms down, not in a T-pose
2. You type a message → Nova replies in the chat panel
3. Nova's mouth animates while the audio plays
4. The avatar blinks naturally and bobs slightly with each breath

**The first reply will be slow.** Ollama loads the model into VRAM on the very first request — this can take 10–30 seconds. Every reply after that is much faster. This is normal.

![Nova responding to "say hi to Codédex" — server logs confirm Edge TTS ✓ and Ollama running](https://raw.githubusercontent.com/JinParkmida/NovaAI/main/assets/sc2.jpg)

> **Note:** If you see `[TTS] SoVITS skipped` in the server logs, that's completely normal. It means the optional high-quality TTS voice cloning module isn't installed, and the server has automatically fallen back to edge-tts. Your audio will still work fine.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Connection refused` on `/api/chat` | Make sure `python app.py` is running in `server/` |
| `model not found` from Ollama | Run `ollama pull llama3.1:8b` and try again |
| Ollama not responding | Run `ollama serve` in a separate terminal |
| Port 7860 already in use | `uvicorn app:app --port 7861` |
| Avatar doesn't appear | Check a `.vrm` file is in `character_files/` and refresh |
| Avatar faces away from camera | The code handles this automatically — make sure you have the VRM version detection block in `loadVRM` |
| Avatar in T-pose | Make sure you have `model.update(0)` in `applyIdlePose` |
| No audio | edge-tts needs an internet connection. Check your network. |
| Audio blocked by browser | Chrome blocks autoplay until user interaction — click the page first |
| CDN import error | Check internet, and verify all five `@pixiv/three-vrm-*` entries are in the import map |
| Slow responses | Use a smaller model (`phi4-mini`, `qwen2.5:3b`) or move to GPU |

---

## Customising Nova

### Change the personality — instantly

Edit `system_prompt` in `character_config.yaml` and send a message. No restart required:

```yaml
presets:
  default:
    system_prompt: |
      You are Nova, a calm and analytical assistant.
      You give precise, factual answers without unnecessary filler.
      When you don't know something, say so directly.
```

### Change the voice

Update `tts.voice` in `character_config.yaml` with any edge-tts voice name:

```yaml
tts:
  voice: en-GB-SoniaNeural   # British
# voice: ja-JP-NanamiNeural  # Japanese
# voice: en-US-JennyNeural   # Softer US English
```

Full list at [speech.microsoft.com/portal/voicegallery](https://speech.microsoft.com/portal/voicegallery).

### Switch the LLM model

Pull a new model and update the config — effective on the next message:

```bash
ollama pull qwen2.5:7b
```

```yaml
llm:
  model: qwen2.5:7b
```

---

## What's Next

The core system is working. Here's where to take it further:

**Fully local voice** — Replace edge-tts with [Piper TTS](https://github.com/rhasspy/piper), which runs entirely offline on your machine. Quality is lower than Microsoft's neural voices, but nothing leaves your machine.

**Tool calling** — Ollama supports OpenAI-format function calling. You can give Nova tools: web search, file read/write, running Python code. The schema format is identical to OpenAI's, so any function-calling tutorial transfers directly.

**Speech input** — Add [faster-whisper](https://github.com/SYSTRAN/faster-whisper) for GPU-accelerated speech-to-text. A microphone + push-to-talk turns Nova into a hands-free assistant.

**Avatar expressions** — The VRM format includes blend shapes for facial expressions (`happy`, `sad`, `surprised`, etc.). You can detect the emotional tone of a response and drive them in real time — making the avatar visually react to what it's saying.

**A live settings panel** — The hot-reload architecture already supports a developer UI. A floating panel with live model selection, personality editing, and voice preview is a natural extension. The backend just needs a `POST /api/settings` endpoint.

---

## Conclusion

What you've built here is a complete local AI companion: a language model running on your own hardware, a text-to-speech voice, a 3D avatar with real-time animations, and a persistent chat history — all wired together in around 300 lines of Python and a single HTML file.

The hot-reload config means you can change Nova's personality, model, or voice between messages without ever restarting the server. The stack is intentionally minimal — one config file, one server file, one HTML file — so every part is understandable and every part is replaceable.

The "What's Next" section above maps out where to go from here: fully offline voice with Piper, speech input with Whisper, emotion expressions, tool calling. Each of those is a meaningful extension of what you already have running. Pick the one that interests you and build it.

---

*Built for the Codédex June 2026 Tutorial Challenge — "Build X with Y"*  
*Stack: Ollama · FastAPI · edge-tts · Three.js · @pixiv/three-vrm*

---

## 🎵 Bonus — Not Part of the Tutorial

This is not a feature. This is a warning.

At some point during testing, I asked Nova to sing Baby Shark. She did. It was terrible. It was also, objectively, hilarious. I am including it here as a cautionary tale about what happens when you give a local language model unrestricted creative freedom and zero musical training.

You built this. You could do the same. Please use this power responsibly.

<video src="https://raw.githubusercontent.com/JinParkmida/NovaAI/main/assets/bonus.mp4" controls width="100%"></video>
