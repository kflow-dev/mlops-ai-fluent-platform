"""Memory storage paths and defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _default_root() -> Path:
    env_root = os.environ.get("AIFLUENT_DATA_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "data"


@dataclass
class MemoryConfig:
    root: Path = field(default_factory=_default_root)

    @property
    def db_path(self) -> Path:
        return self.root / "memory.db"

    @property
    def blob_dir(self) -> Path:
        return self.root / "blobs"

    @property
    def chat_dir(self) -> Path:
        return self.root / "chat_sessions"

    def ensure_dirs(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.blob_dir.mkdir(parents=True, exist_ok=True)
        self.chat_dir.mkdir(parents=True, exist_ok=True)


_default: MemoryConfig | None = None


def get_default_memory_config() -> MemoryConfig:
    global _default
    current_root = _default_root()
    if _default is None or _default.root != current_root:
        _default = MemoryConfig(root=current_root)
        _default.ensure_dirs()
    return _default
