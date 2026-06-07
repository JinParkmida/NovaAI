"""
main_chat.py — Nova: unified text + voice assistant (tutorial version)

Usage:
  python main_chat.py              # default: text mode, no TTS
  python main_chat.py --voice      # voice input (push-to-talk), TTS output
  python main_chat.py --text       # text input, TTS output
  python main_chat.py --no-tts     # text input, no TTS (fastest for dev)
  python main_chat.py --web        # browser UI with VRM avatar

Commands (in any mode):
  quit / exit / bye    — exit
  clear                — wipe conversation history
  help                 — show commands
"""

import argparse
import sys
import uuid
import yaml
from pathlib import Path

# ── Resolve paths ──────────────────────────────────────────────────────────────
SERVER_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SERVER_DIR))

CONFIG_PATH = SERVER_DIR.parent / "character_config.yaml"
with open(CONFIG_PATH, "r") as f:
    _config = yaml.safe_load(f)

_tts_cfg  = _config.get("tts", {})
TTS_PRIMARY  = _tts_cfg.get("primary",  "edge-tts")

AUDIO_DIR = SERVER_DIR / "audio"
AUDIO_DIR.mkdir(exist_ok=True)


# ── Lazy imports ───────────────────────────────────────────────────────────────

def _load_llm():
    from process.llm_funcs.llm_scr import llm_response, clear_history
    return llm_response, clear_history


def _load_asr():
    from process.asr_func.asr_push_to_talk import load_whisper_model, record_and_transcribe
    return load_whisper_model, record_and_transcribe


def _load_tts():
    from process.tts_func.edge_tts_func import edge_gen

    def speak(text: str) -> None:
        uid  = uuid.uuid4().hex[:8]
        mp3  = AUDIO_DIR / f"nova_{uid}.mp3"
        path = edge_gen(text, mp3)
        if path:
            import subprocess, sys as _sys
            if _sys.platform == "win32":
                subprocess.Popen(["start", "", str(path)], shell=True)
            else:
                subprocess.Popen(["xdg-open", str(path)])
        else:
            print("[TTS] Edge TTS unavailable — text only.")

        for f in AUDIO_DIR.glob("nova_*.mp3"):
            try: f.unlink()
            except OSError: pass

    return speak


# ── Helpers ────────────────────────────────────────────────────────────────────

BANNER = r"""
 _   _
| \ | | _____   ____ _
|  \| |/ _ \ \ / / _` |
| |\  | (_) \ V / (_| |
|_| \_|\___/ \_/ \__,_|   ~ your offline AI companion

"""

HELP_TEXT = """
Commands:
  quit / exit / bye   — exit Nova
  clear               — reset conversation memory
  help                — show this message
"""


def handle_command(cmd: str, clear_history_fn) -> bool:
    c = cmd.strip().lower()
    if c in ("quit", "exit", "bye"):
        print("Nova: See you later~ 👋")
        sys.exit(0)
    if c == "clear":
        clear_history_fn()
        print("[Memory cleared]")
        return True
    if c == "help":
        print(HELP_TEXT)
        return True
    return False


# ── Modes ──────────────────────────────────────────────────────────────────────

def run_text_mode(tts_enabled: bool) -> None:
    llm_response, clear_history = _load_llm()
    speak = _load_tts() if tts_enabled else None

    print(BANNER)
    print("Text mode — type your message, press Enter to send.")
    print('Type "help" for commands.\n')

    while True:
        try:
            user_in = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nNova: Bye~")
            break

        if not user_in:
            continue
        if handle_command(user_in, clear_history):
            continue

        reply = llm_response(user_in)
        print(f"\nNova: {reply}\n")
        if speak:
            speak(reply)


def run_voice_mode(tts_enabled: bool) -> None:
    llm_response, clear_history = _load_llm()
    load_whisper_model, record_and_transcribe = _load_asr()
    speak = _load_tts() if tts_enabled else None

    print(BANNER)
    print("Voice mode — push-to-talk. Press ENTER to start/stop recording.")
    print('Say "quit" or press Ctrl+C to exit.\n')

    whisper  = load_whisper_model()
    wav_path = AUDIO_DIR / "conversation.wav"

    while True:
        try:
            user_in = record_and_transcribe(whisper, wav_path)
        except KeyboardInterrupt:
            print("\nNova: Bye~")
            break

        if not user_in:
            print("[No speech detected, try again]")
            continue
        if handle_command(user_in, clear_history):
            continue

        reply = llm_response(user_in)
        print(f"\nNova: {reply}\n")
        if speak:
            speak(reply)


def run_web_mode(port: int = 7860, no_browser: bool = False) -> None:
    try:
        import uvicorn
    except ImportError:
        print("[Error] uvicorn not installed. Run: pip install fastapi uvicorn")
        sys.exit(1)

    if not no_browser:
        import threading, webbrowser, time
        def _open():
            time.sleep(1.2)
            webbrowser.open(f"http://localhost:{port}")
        threading.Thread(target=_open, daemon=True).start()

    print(BANNER)
    print(f"Web UI: http://localhost:{port}")
    print("Press Ctrl+C to stop.\n")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Nova — offline AI companion (tutorial version)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--web",   action="store_true", help="Web UI mode (browser with VRM avatar)")
    group.add_argument("--voice", action="store_true", help="Voice input mode (push-to-talk)")
    group.add_argument("--text",  action="store_true", help="Text input mode")
    parser.add_argument("--no-tts",    action="store_true", help="Disable TTS output")
    parser.add_argument("--port",      type=int, default=7860, help="Port for web mode")
    parser.add_argument("--no-browser",action="store_true",   help="Don't auto-open browser")
    args = parser.parse_args()

    tts_on = not args.no_tts

    if args.web:
        run_web_mode(port=args.port, no_browser=args.no_browser)
    elif args.voice:
        run_voice_mode(tts_enabled=tts_on)
    else:
        run_text_mode(tts_enabled=tts_on)


if __name__ == "__main__":
    main()
