import ast
from pathlib import Path

class CodeAnalyzer:
    """
    Static code analysis for Python projects.
    Can be extended for JS/TS in the future.
    """

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.analysis_results = {}

    def analyze_file(self, file_path: Path):
        if not file_path.exists() or file_path.suffix != ".py":
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        try:
            tree = ast.parse(source)
            num_functions = len([n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)])
            num_classes = len([n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)])
            self.analysis_results[str(file_path)] = {
                "functions": num_functions,
                "classes": num_classes,
            }
        except Exception as e:
            self.analysis_results[str(file_path)] = {"error": str(e)}

    def analyze_repo(self):
        for file_path in self.repo_path.rglob("*.py"):
            self.analyze_file(file_path)
        return self.analysis_results
