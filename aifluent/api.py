import os
from pathlib import Path
from typing import Optional, Union

from fastapi import FastAPI
from fastapi import HTTPException
from pydantic import BaseModel
import yaml

from aifluent.chat.service import ChatMessage
from aifluent.chat.service import chat_completion
from aifluent.chat.service import delete_chat_session
from aifluent.chat.service import list_chat_sessions
from aifluent.chat.service import load_chat_session
from aifluent.chat.service import save_chat_session
from aifluent.core.model_manager import ModelManager
from aifluent.core.model_manager import _resolve_ollama_model_path
from aifluent.core.agent import BaseAgent
from aifluent.core.swarm_orchestrator import SwarmOrchestrator
from aifluent.core.refactor_engine import RefactorEngine
from aifluent.memory.web import router as memory_router

app = FastAPI(title="AIFluent API")
app.include_router(memory_router)

model_manager: Optional[ModelManager] = None
agent: Optional[BaseAgent] = None
swarm: Optional[SwarmOrchestrator] = None
refactor_engine: Optional[RefactorEngine] = None


def _config_path() -> Path:
    return Path(os.environ.get("AIFLUENT_MODEL_CONFIG", "config/models.yaml"))


def _env_path() -> Path:
    return Path(".env")


def _display_path(path: Union[Path, str]) -> str:
    path_obj = Path(path)
    try:
        rel = path_obj.resolve().relative_to(Path.cwd().resolve())
        return str(rel)
    except Exception:
        return path_obj.name if path_obj.name else str(path_obj)


def _display_model_path(path: str) -> str:
    path_obj = Path(path)
    parts = path_obj.parts
    if "blobs" in parts:
        return f"<local-model-store>/blobs/{path_obj.name}"
    return _display_path(path_obj)


def _read_env_file() -> dict[str, str]:
    env: dict[str, str] = {}
    path = _env_path()
    if not path.exists():
        return env
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def _write_env_file(values: dict[str, str]) -> None:
    lines = [f"{key}={value}" for key, value in values.items()]
    _env_path().write_text("\n".join(lines) + "\n", encoding="utf-8")


def _runtime_status() -> dict:
    return {
        "config_path": _display_path(_config_path()),
        "data_root": _display_path(os.environ.get("AIFLUENT_DATA_ROOT", "data")),
        "active_models": [
            {"name": model.name, "type": model.type, "path": _display_model_path(model.path)}
            for model in (model_manager.active_models if model_manager else [])
        ],
        "voting_threshold": model_manager.voting_threshold if model_manager else None,
    }


def reload_runtime() -> dict:
    global model_manager, agent, swarm, refactor_engine
    manager = ModelManager()
    manager.select_models()
    manager.load_active_models()
    runtime_agent = BaseAgent("Agent-API", manager)
    runtime_swarm = SwarmOrchestrator([runtime_agent], voting_threshold=manager.voting_threshold)
    runtime_refactor_engine = RefactorEngine(manager)

    model_manager = manager
    agent = runtime_agent
    swarm = runtime_swarm
    refactor_engine = runtime_refactor_engine
    return _runtime_status()


reload_runtime()

class RepoPath(BaseModel):
    repo: str

class FilePath(BaseModel):
    file: str


class ChatRequest(BaseModel):
    message: Optional[str] = None
    messages: list[dict] = []
    model: Optional[str] = None
    system: Optional[str] = None


class ChatSessionSaveRequest(BaseModel):
    tag: str
    messages: list[dict]
    model: Optional[str] = None


class ModelsConfigUpdate(BaseModel):
    content: str
    reload: bool = True


class EnvSettingsUpdate(BaseModel):
    aifluent_model_config: str = "config/models.yaml"
    aifluent_data_root: str = "data"
    reload: bool = True


class ConfigValidationRequest(BaseModel):
    content: str
    aifluent_model_config: str = "config/models.yaml"
    aifluent_data_root: str = "data"


def _validate_models_yaml(content: str) -> dict:
    try:
        parsed = yaml.safe_load(content) or {}
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {exc}") from exc

    if not isinstance(parsed.get("models"), list) or not parsed["models"]:
        raise HTTPException(status_code=400, detail="Config must contain a non-empty 'models' list.")
    return parsed


def _validate_model_entries(parsed: dict) -> list[dict]:
    validated_models = []
    unresolved = []

    for item in parsed["models"]:
        name = item.get("name")
        model_type = item.get("type")
        path = item.get("path")
        resolved_path = path

        if not name or not model_type:
            unresolved.append("Each model entry must include both 'name' and 'type'.")
            continue

        if model_type == "ollama":
            resolved = _resolve_ollama_model_path(str(name))
            if resolved is None:
                unresolved.append(f"Ollama model '{name}' is not installed or could not be resolved locally.")
            else:
                resolved_path = str(resolved)

        validated_models.append(
            {
                "name": name,
                "type": model_type,
                "path": path,
                "resolved_path": resolved_path,
            }
        )

    if unresolved:
        raise HTTPException(status_code=400, detail=" ".join(unresolved))

    return validated_models


@app.get("/config/models")
def get_models_config():
    config_path = _config_path()
    if not config_path.exists():
        raise HTTPException(status_code=404, detail=f"Config file not found: {_display_path(config_path)}")
    return {
        "path": _display_path(config_path),
        "content": config_path.read_text(encoding="utf-8"),
        "runtime": _runtime_status(),
    }


@app.post("/config/models")
def save_models_config(payload: ModelsConfigUpdate):
    parsed = _validate_models_yaml(payload.content)
    _validate_model_entries(parsed)

    config_path = _config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(payload.content, encoding="utf-8")

    runtime = _runtime_status()
    if payload.reload:
        try:
            runtime = reload_runtime()
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Config saved, but reload failed: {exc}",
            ) from exc

    return {"status": "ok", "path": _display_path(config_path), "runtime": runtime}


@app.post("/config/validate")
def validate_config(payload: ConfigValidationRequest):
    parsed = _validate_models_yaml(payload.content)
    validated_models = _validate_model_entries(parsed)
    return {
        "status": "ok",
        "config_path": _display_path(payload.aifluent_model_config),
        "data_root": _display_path(payload.aifluent_data_root),
        "model_count": len(validated_models),
        "models": validated_models,
    }


@app.get("/config/env")
def get_env_config():
    env = _read_env_file()
    return {
        "path": _display_path(_env_path()),
        "values": {
            "AIFLUENT_MODEL_CONFIG": env.get("AIFLUENT_MODEL_CONFIG", "config/models.yaml"),
            "AIFLUENT_DATA_ROOT": env.get("AIFLUENT_DATA_ROOT", "data"),
        },
        "runtime": _runtime_status(),
    }


@app.post("/config/env")
def save_env_config(payload: EnvSettingsUpdate):
    values = _read_env_file()
    values["AIFLUENT_MODEL_CONFIG"] = payload.aifluent_model_config.strip() or "config/models.yaml"
    values["AIFLUENT_DATA_ROOT"] = payload.aifluent_data_root.strip() or "data"
    _write_env_file(values)

    os.environ["AIFLUENT_MODEL_CONFIG"] = values["AIFLUENT_MODEL_CONFIG"]
    os.environ["AIFLUENT_DATA_ROOT"] = values["AIFLUENT_DATA_ROOT"]

    runtime = _runtime_status()
    if payload.reload:
        try:
            runtime = reload_runtime()
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f".env saved, but reload failed: {exc}",
            ) from exc

    return {
        "status": "ok",
        "path": _display_path(_env_path()),
        "values": values,
        "runtime": runtime,
    }


@app.post("/analyze")
def analyze_repo(repo: RepoPath):
    assert agent is not None
    agent.analyze_code(repo.repo)
    return {"status": "analyzed", "repo": repo.repo}

@app.post("/refactor")
def refactor_file(file: FilePath):
    assert swarm is not None
    suggestion = swarm.refactor_file(file.file)
    return {"status": "refactor_applied" if suggestion else "no_consensus", "file": file.file}

@app.post("/test")
def generate_tests(repo: RepoPath):
    from aifluent.core.test_generator import TestGenerator
    tg = TestGenerator(repo.repo)
    tg.generate_tests()
    return {"status": "tests_generated", "repo": repo.repo}


@app.post("/chat")
def chat(payload: ChatRequest):
    chat_messages: list[ChatMessage] = []
    if payload.messages:
        for item in payload.messages:
            role = item.get("role")
            content = item.get("content")
            if role and content:
                chat_messages.append(ChatMessage(role=role, content=content))
    elif payload.message:
        chat_messages.append(ChatMessage(role="user", content=payload.message))

    if not chat_messages:
        raise HTTPException(status_code=400, detail="A message or messages array is required.")

    try:
        response = chat_completion(
            messages=chat_messages,
            model=payload.model,
            system_prompt=payload.system,
            model_manager=model_manager,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Chat request failed: {exc}") from exc

    return response


@app.get("/chat/sessions")
def get_chat_sessions():
    return list_chat_sessions()


@app.get("/chat/sessions/{tag}")
def get_chat_session(tag: str):
    try:
        return load_chat_session(tag)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/chat/sessions")
def create_chat_session(payload: ChatSessionSaveRequest):
    messages = [ChatMessage(role=item.get("role", ""), content=item.get("content", "")) for item in payload.messages if item.get("role") and item.get("content")]
    try:
        path = save_chat_session(payload.tag, messages, model=payload.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "path": _display_path(path)}


@app.delete("/chat/sessions/{tag}")
def remove_chat_session(tag: str):
    try:
        delete_chat_session(tag)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "ok"}
