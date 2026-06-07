<div align="center">

```
 _   _
| \ | | _____   ____ _
|  \| |/ _ \ \ / / _` |
| |\  | (_) \ V / (_| |
|_| \_|\___/ \_/ \__,_|
```

### Your fully local AI companion — 3D avatar, voice, and memory. No cloud required.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Three.js](https://img.shields.io/badge/Three.js-r163-black?style=flat-square&logo=threedotjs&logoColor=white)](https://threejs.org)
[![Ollama](https://img.shields.io/badge/Ollama-local_LLM-FF6B35?style=flat-square)](https://ollama.com)

</div>

---

Nova is an AI companion that runs entirely on your own hardware. She has a 3D avatar that blinks, breathes, and moves her mouth when she speaks. Her voice is synthesised through Microsoft's free Neural TTS. Her memory persists across sessions. And she runs on a local LLM through Ollama — no API keys, no usage limits, no data leaving your machine.

> **This is the tutorial version** — a clean, focused codebase built for learning. For the full production build with persistent user memory, live emotion reactions, and an evolving personality system, see the root project.

<br>

## ✨ What Nova Can Do

| Feature | How it works |
|---------|-------------|
| 🎴 **3D avatar** | VRM model rendered in-browser with Three.js + springbone physics |
| 💬 **Persistent chat** | Rolling conversation history across sessions |
| 🔊 **Voice synthesis** | Microsoft Edge TTS — free, no API key, 40+ voices |
| 🧠 **Local LLM** | Ollama running llama3.1:8b (or any model you pull) |
| ⚙️ **Live config** | Change the model, personality, and voice mid-session without restarting |
| 📱 **Responsive UI** | Works on desktop and mobile |

<br>

## 🛠️ Prerequisites

Before you start, make sure you have these installed:

- **Python 3.11+** — [python.org](https://python.org)
- **Ollama** — [ollama.com](https://ollama.com) · then run `ollama pull llama3.1:8b`
- **A VRM avatar** — drop one into `character_files/` (see below)

<br>

## 🚀 Quick Start

**1. Clone or download this folder**

**2. Install dependencies**

```bash
pip install fastapi uvicorn openai pyyaml edge-tts requests
```

**3. Get a VRM model**

Download a free avatar from [VRoid Hub](https://hub.vroid.com) and place the `.vrm` file in `character_files/`. Then update `character_config.yaml`:

```yaml
character:
  vrm_model: YourModel.vrm   # ← filename you just placed there
```

**4. Make sure Ollama is running**

```bash
ollama serve
```

**5. Launch Nova**

```bash
# Windows — double-click run.bat, or:
python server/main_chat.py --web

# macOS / Linux
cd server && python main_chat.py --web
```

Open **http://localhost:7860** in your browser. That's it.

<br>

## 🗂️ Project Structure

```
nova-tutorial/
│
├── character_config.yaml     ← all settings live here (hot-reloaded)
├── run.bat                   ← Windows one-click launcher
│
├── character_files/
│   └── YourModel.vrm         ← your VRM avatar goes here
│
├── client/
│   └── index.html            ← the entire frontend (no build step)
│
├── data/
│   └── chat_history.json     ← conversation memory (auto-created)
│
└── server/
    ├── main_chat.py          ← entry point (web / text / voice modes)
    ├── app.py                ← FastAPI backend + TTS chain
    └── process/
        ├── llm_funcs/
        │   └── llm_scr.py    ← LLM calls + history management
        └── tts_func/
            └── edge_tts_func.py  ← Microsoft Neural TTS
```

<br>

## ⚙️ Configuration

Everything is controlled from `character_config.yaml`. Changes take effect on the **next message** — no restart needed.

```yaml
llm:
  model: llama3.1:8b          # any Ollama model you have pulled
  temperature: 0.85           # 0 = focused, 2 = chaotic
  max_tokens: 1024

character:
  name: Nova
  vrm_model: Yoon.vrm         # filename inside character_files/

presets:
  default:
    system_prompt: |
      You are Nova, a helpful and witty AI companion...
```

You can also edit everything through the **Developer Panel** in the browser (`Ctrl+,`).

<br>

## 🔊 Changing the Voice

Nova uses [Microsoft Edge TTS](https://speech.microsoft.com/portal/voicegallery) — free, online, 400+ voices across 140 languages. To preview and switch voices, open the Developer Panel → Voice tab.

Some good options:

| Voice | Character |
|-------|-----------|
| `en-US-AriaNeural` | Warm, natural (default) |
| `en-US-JennyNeural` | Soft and friendly |
| `en-GB-SoniaNeural` | British accent |
| `ja-JP-NanamiNeural` | Japanese female |

<br>

## 💬 Running Modes

```bash
python server/main_chat.py --web        # browser UI with 3D avatar
python server/main_chat.py --text       # terminal REPL + TTS
python server/main_chat.py --no-tts     # terminal REPL only (fastest)
python server/main_chat.py --voice      # push-to-talk with Whisper ASR
```

<br>

## 🏗️ How It Works

```
You type a message
      │
      ▼
POST /api/chat  (FastAPI)
      │
      ▼
llm_response()  ← loads chat history + system prompt
      │           sends to Ollama (OpenAI-compatible API)
      │           saves updated history to disk
      ▼
TTS chain:  Edge TTS → returns MP3
      │
      ▼
Browser:  renders message → plays audio → avatar mouth moves
```

The frontend is a single `index.html` file — no npm, no bundler. Three.js and the VRM loader are imported directly from CDN via ES module import maps.

<br>

## 🎴 About VRM Models

VRM is an open format for 3D humanoid avatars, widely used in VTubing and virtual worlds. You can:

- **Download free models** from [VRoid Hub](https://hub.vroid.com) (look for models with a CC0 or personal-use license)
- **Create your own** with [VRoid Studio](https://vroid.com/en/studio) — free, no 3D experience needed
- **Use any VRM 0.x or 1.x model** — Nova detects the version automatically and applies the correct coordinate fix

<br>

---

<div align="center">

Built with [Ollama](https://ollama.com) · [FastAPI](https://fastapi.tiangolo.com) · [Three.js](https://threejs.org) · [edge-tts](https://github.com/rany2/edge-tts) · [@pixiv/three-vrm](https://github.com/pixiv/three-vrm)

*Made for the [Codédex](https://www.codedex.io) community*

</div>
