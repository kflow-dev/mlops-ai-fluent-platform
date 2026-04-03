from typing import List, Dict
from aifluent.core.model_manager import ModelManager

class BaseAgent:
    def __init__(self, name: str, model_manager: ModelManager):
        self.name = name
        self.model_manager = model_manager
        self.session_memory: Dict = {}  # Session-only context

    def analyze_code(self, repo_path: str):
        print(f"[{self.name}] Analyzing repo at {repo_path}")
        # Placeholder: could integrate AST parsing, code metrics

    def suggest_refactor(self, file_path: str):
        print(f"[{self.name}] Suggesting refactor for {file_path}")
        # Placeholder: produce LLM suggestions from active models

    def execute_action(self, action: str, **kwargs):
        if action == "analyze":
            self.analyze_code(kwargs.get("repo_path", "."))
        elif action == "refactor":
            self.suggest_refactor(kwargs.get("file_path", ""))
