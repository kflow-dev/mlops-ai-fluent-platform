from pathlib import Path

class TestGenerator:
    """
    Generates basic pytest skeletons for Python modules
    """

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)

    def generate_tests(self):
        test_dir = self.repo_path / "tests"
        test_dir.mkdir(exist_ok=True)
        for py_file in self.repo_path.rglob("*.py"):
            if py_file.name.startswith("test_"):
                continue
            test_file = test_dir / f"test_{py_file.stem}.py"
            if not test_file.exists():
                content = f"""import pytest
from {py_file.stem} import *

def test_placeholder():
    assert True  # TODO: Implement tests for {py_file.name}
"""
                test_file.write_text(content)
                print(f"[TESTGEN] Generated {test_file}")
