from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from aifluent.core.model_manager import ModelManager
from aifluent.memory.config import get_default_memory_config


@dataclass
class ChatMessage:
    role: str
    content: str


def _chat_dir() -> Path:
    cfg = get_default_memory_config()
    return cfg.chat_dir


def _safe_tag(tag: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in tag.strip())
    cleaned = cleaned.strip("-_")
    if not cleaned:
        raise ValueError("Chat tag must contain letters, digits, '-' or '_'.")
    return cleaned


def save_chat_session(tag: str, messages: list[ChatMessage], model: Optional[str] = None) -> Path:
    safe_tag = _safe_tag(tag)
    path = _chat_dir() / f"{safe_tag}.json"
    payload = {
        "tag": safe_tag,
        "saved_at": datetime.utcnow().isoformat() + "Z",
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_chat_session(tag: str) -> dict:
    safe_tag = _safe_tag(tag)
    path = _chat_dir() / f"{safe_tag}.json"
    if not path.exists():
        raise FileNotFoundError(f"Chat session not found: {safe_tag}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_chat_sessions() -> list[dict]:
    sessions = []
    for path in sorted(_chat_dir().glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            sessions.append(
                {
                    "tag": payload.get("tag", path.stem),
                    "saved_at": payload.get("saved_at"),
                    "model": payload.get("model"),
                    "message_count": len(payload.get("messages", [])),
                }
            )
        except Exception:
            continue
    return sessions


def delete_chat_session(tag: str) -> None:
    safe_tag = _safe_tag(tag)
    path = _chat_dir() / f"{safe_tag}.json"
    if not path.exists():
        raise FileNotFoundError(f"Chat session not found: {safe_tag}")
    path.unlink()


def _ollama_base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")


def _default_model_name(model_manager: Optional[ModelManager] = None) -> str:
    manager = model_manager or ModelManager()
    manager.select_models()
    if not manager.active_models:
        raise RuntimeError("No active models are configured.")
    return manager.active_models[0].name


def chat_completion(
    messages: list[ChatMessage],
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    model_manager: Optional[ModelManager] = None,
    timeout: float = 60.0,
) -> dict:
    if not messages:
        raise ValueError("At least one chat message is required.")

    chosen_model = model or _default_model_name(model_manager)
    payload_messages = []
    if system_prompt:
        payload_messages.append({"role": "system", "content": system_prompt})
    payload_messages.extend({"role": m.role, "content": m.content} for m in messages)

    response = requests.post(
        f"{_ollama_base_url()}/api/chat",
        json={"model": chosen_model, "messages": payload_messages, "stream": False},
        timeout=timeout,
    )
    response.raise_for_status()
    body = response.json()
    message = body.get("message", {})
    return {
        "model": chosen_model,
        "message": {
            "role": message.get("role", "assistant"),
            "content": message.get("content", ""),
        },
        "done": body.get("done", True),
        "raw": body,
    }
