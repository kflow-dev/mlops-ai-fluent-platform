from __future__ import annotations

from pathlib import Path
from typing import Optional

from aifluent.core.model_manager import ModelManager
from aifluent.core.refactor_engine import RefactorEngine


def suggest_inline_refactor(
    file_path: str,
    model_manager: Optional[ModelManager] = None,
) -> str | None:
    """Return a placeholder refactor suggestion for a Python file."""
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    manager = model_manager or ModelManager()
    engine = RefactorEngine(manager)
    return engine.suggest_refactor(str(path))


if __name__ == "__main__":
    target = "aifluent/cli.py"
    suggestion = suggest_inline_refactor(target)
    if suggestion:
        print(suggestion)
