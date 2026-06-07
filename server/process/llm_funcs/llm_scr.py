"""
llm_scr.py — Nova's LLM brain (tutorial version).

Simple chat with rolling history. No tools, no memory extraction,
no personality state, no emotion detection.

Config is hot-reloaded on every call — changes to character_config.yaml
take effect immediately on the next message.

Returns: str — the reply text.
"""

import yaml
import json
from datetime import datetime
from openai import OpenAI
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────

CONFIG_PATH = Path(__file__).parents[3] / "character_config.yaml"


def _reload_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── OpenAI client (cached) ─────────────────────────────────────────────────────

_client_cache: dict = {"base_url": None, "api_key": None, "client": None}


def _get_client(llm_cfg: dict) -> OpenAI:
    global _client_cache
    url = llm_cfg["base_url"]
    key = llm_cfg.get("api_key", "ollama")
    if _client_cache["base_url"] != url or _client_cache["api_key"] != key:
        _client_cache = {
            "base_url": url,
            "api_key":  key,
            "client":   OpenAI(base_url=url, api_key=key),
        }
    return _client_cache["client"]


# ── System prompt ──────────────────────────────────────────────────────────────

def _build_system_prompt(cfg: dict) -> str:
    char_cfg = cfg.get("character", {})
    presets  = cfg.get("presets", {})
    preset   = presets.get(char_cfg.get("preset", "default"), {})
    prompt   = preset.get("system_prompt", "You are a helpful assistant.")
    now      = datetime.now().strftime("%A, %B %d %Y — %H:%M")
    return f"[Current time: {now}]\n\n{prompt.strip()}"


# ── History ────────────────────────────────────────────────────────────────────

def _get_history_file(cfg: dict) -> Path:
    mem_cfg     = cfg.get("memory", {})
    history_rel = mem_cfg.get("history_file", "./data/chat_history.json")
    history_file = CONFIG_PATH.parent / history_rel
    history_file.parent.mkdir(parents=True, exist_ok=True)
    return history_file


def load_history(history_file: Path | None = None, max_msgs: int = 40) -> list[dict]:
    if history_file is None:
        cfg = _reload_config()
        history_file = _get_history_file(cfg)
        max_msgs = cfg.get("memory", {}).get("max_history_messages", 40)
    if history_file.exists():
        with open(history_file, "r", encoding="utf-8") as f:
            history = json.load(f)
        if len(history) > max_msgs:
            history = history[-max_msgs:]
        return history
    return []


def save_history(history: list[dict], history_file: Path | None = None) -> None:
    if history_file is None:
        cfg = _reload_config()
        history_file = _get_history_file(cfg)
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def clear_history() -> None:
    cfg = _reload_config()
    history_file = _get_history_file(cfg)
    if history_file.exists():
        history_file.unlink()
    print("[Memory cleared]")


# ── LLM response ───────────────────────────────────────────────────────────────

def llm_response(user_input: str) -> str:
    """
    Single LLM turn. Returns reply text.

    1. Hot-reload config
    2. Build system prompt
    3. Load chat history
    4. Call LLM
    5. Save updated history
    """
    cfg     = _reload_config()
    llm_cfg = cfg.get("llm", {})
    mem_cfg = cfg.get("memory", {})

    client      = _get_client(llm_cfg)
    model       = llm_cfg.get("model",       "llama3.1:8b")
    temperature = llm_cfg.get("temperature",  0.85)
    max_tokens  = llm_cfg.get("max_tokens",   1024)

    history_file = _get_history_file(cfg)
    max_history  = mem_cfg.get("max_history_messages", 40)

    messages = load_history(history_file, max_history)
    messages.append({"role": "user", "content": user_input})

    full_messages = [
        {"role": "system", "content": _build_system_prompt(cfg)},
        *messages,
    ]

    response = client.chat.completions.create(
        model       = model,
        messages    = full_messages,
        temperature = temperature,
        max_tokens  = max_tokens,
    )

    reply = response.choices[0].message.content or ""
    messages.append({"role": "assistant", "content": reply})
    save_history(messages, history_file)

    return reply


# ── CLI convenience ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Nova text mode (type 'quit' to exit, 'clear' to reset memory)\n")

    while True:
        try:
            user_in = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nNova: Bye~")
            break

        if not user_in:
            continue
        if user_in.lower() in ("quit", "exit", "bye"):
            print("Nova: See you later.")
            break
        if user_in.lower() == "clear":
            clear_history()
            continue

        reply = llm_response(user_in)
        print(f"Nova: {reply}\n")
