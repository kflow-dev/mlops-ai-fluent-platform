from pathlib import Path

from aifluent.core.model_manager import ModelManager

class RefactorEngine:
    """
    Provides refactoring suggestions for Python files using LLMs
    """

    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager

    def suggest_refactor(self, file_path: str):
        path = Path(file_path)
        if not path.exists() or path.suffix != ".py":
            return None
        # Placeholder: LLM-based refactoring logic
        suggestion = f"# Suggested refactor for {file_path} by LLMs"
        return suggestion

    def apply_refactor(self, file_path: str, suggestion: str):
        # Simple placeholder write; in real implementation could apply diff/patch
        path = Path(file_path)
        if path.exists():
            with open(path, "a", encoding="utf-8") as f:
                f.write("\n\n" + suggestion)
            print(f"[REFACTOR] Applied suggestion to {file_path}")
