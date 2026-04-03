import os
import re
from pathlib import Path
from typing import Any, Iterable, List, Optional

import yaml


def _normalize_model_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _display_model_path(path: str) -> str:
    path_obj = Path(path)
    parts = path_obj.parts
    if "blobs" in parts:
        return f"<local-model-store>/blobs/{path_obj.name}"
    return path_obj.name if path_obj.name else str(path_obj)


def _ollama_roots() -> list[Path]:
    candidates = [
        os.environ.get("OLLAMA_MODELS"),
        str(Path.home() / ".ollama" / "models"),
        "/usr/share/ollama/.ollama/models",
        "/opt/homebrew/var/lib/ollama/models",
        str(Path.home() / ".local" / "share" / "ollama" / "models"),
    ]
    roots: list[Path] = []
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser().resolve()
        if path.exists() and path not in roots:
            roots.append(path)
    return roots


def _iter_ollama_manifests() -> Iterable[tuple[str, Path]]:
    for root in _ollama_roots():
        manifests_root = root / "manifests"
        if not manifests_root.exists():
            continue
        for manifest in manifests_root.rglob("*"):
            if manifest.is_file():
                yield str(manifest.relative_to(manifests_root)), manifest


def _ollama_blob_path(models_root: Path, digest: str) -> Optional[Path]:
    if not digest.startswith("sha256:"):
        return None
    blob = models_root / "blobs" / digest.replace(":", "-")
    return blob if blob.exists() else None


def _resolve_ollama_model_path(model_name: str) -> Optional[Path]:
    target = _normalize_model_name(model_name)
    matches: list[tuple[int, str, Path, Path]] = []
    for manifest_rel, manifest_path in _iter_ollama_manifests():
        rel_parts = manifest_rel.split("/")
        installed_name = rel_parts[-2] if len(rel_parts) >= 2 else manifest_rel
        installed_tag = rel_parts[-1]
        normalized_installed = _normalize_model_name(installed_name)
        if target == normalized_installed:
            score = 300
        elif target in normalized_installed or normalized_installed in target:
            score = 200
        else:
            continue
        if installed_tag == "latest":
            score += 25
        try:
            import json

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        model_layer = next(
            (layer for layer in manifest.get("layers", []) if layer.get("mediaType") == "application/vnd.ollama.image.model"),
            None,
        )
        if not model_layer:
            continue
        models_root = manifest_path.parents[len(rel_parts)]
        blob_path = _ollama_blob_path(models_root, model_layer.get("digest", ""))
        if not blob_path:
            continue
        matches.append((score, manifest_rel, manifest_path, blob_path))

    if not matches:
        return None

    matches.sort(key=lambda item: (-item[0], len(item[1])))
    return matches[0][3]


class Model:
    def __init__(self, name, type_, path, capabilities, priority):
        self.name = name
        self.type = type_
        self.path = path
        self.capabilities = capabilities
        self.priority = priority
        self.loaded = False

    def load(self):
        # Placeholder for real LLM loading logic (Ollama, llama.cpp, GPT4All)
        print(f"[MODEL] Loading {self.name} from {_display_model_path(self.path)}")
        self.loaded = True


class ModelManager:
    def __init__(self, config_path="config/models.yaml"):
        env_config_path = os.environ.get("AIFLUENT_MODEL_CONFIG")
        resolved_path = env_config_path or config_path
        self.config_path = Path(resolved_path)
        self.models: List[Model] = []
        self.load_config()
        self.active_models: List[Model] = []

    def load_config(self):
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Model config not found: {self.config_path}. "
                "Create config/models.yaml or pass a valid config path."
            )

        with self.config_path.open("r", encoding="utf-8") as f:
            cfg: dict[str, Any] = yaml.safe_load(f) or {}

        models = cfg.get("models")
        if not isinstance(models, list) or not models:
            raise ValueError(
                f"Invalid model config in {self.config_path}: expected a non-empty 'models' list."
            )

        self.models = []
        for m in models:
            model_type = m["type"]
            model_path = m["path"]
            if model_type == "ollama":
                resolved = _resolve_ollama_model_path(m["name"])
                if resolved is not None:
                    model_path = str(resolved)
            self.models.append(Model(
                name=m["name"],
                type_=model_type,
                path=model_path,
                capabilities=m["capabilities"],
                priority=m["priority"]
            ))
        self.voting_threshold = cfg.get("settings", {}).get("voting_threshold", 0.6)
        self.max_active_models = cfg.get("settings", {}).get("max_active_models", 3)

    def detect_vram(self):
        # macOS VRAM detection placeholder
        print(f"[MODEL] Detecting available VRAM...")
        return 128  # Assume 128 GB for your setup

    def select_models(self):
        # Prioritize by defined priority
        self.models.sort(key=lambda m: m.priority, reverse=True)
        self.active_models = self.models[:self.max_active_models]
        print(f"[MODEL] Active models: {[m.name for m in self.active_models]}")

    def load_active_models(self):
        for m in self.active_models:
            m.load()
