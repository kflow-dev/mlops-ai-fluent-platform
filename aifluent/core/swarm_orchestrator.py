import random
from typing import List

from aifluent.core.agent import BaseAgent

class SwarmOrchestrator:
    """
    Multi-agent orchestration using MoE + dynamic voting
    """

    def __init__(self, agents: List[BaseAgent], voting_threshold: float = 0.6):
        self.agents = agents
        self.voting_threshold = voting_threshold

    def refactor_file(self, file_path: str):
        votes = []
        suggestions = []

        for agent in self.agents:
            suggestion = agent.suggest_refactor(file_path)
            if suggestion:
                suggestions.append(suggestion)
                votes.append(random.random())  # Placeholder for real confidence score

        # MoE decision logic
        avg_vote = sum(votes) / max(len(votes), 1)
        if avg_vote >= self.voting_threshold:
            print(f"[SWARM] Applying refactor to {file_path}")
            # Apply best suggestion (simplified)
            return suggestions[0]
        else:
            print(f"[SWARM] No consensus reached for {file_path}")
            return None
