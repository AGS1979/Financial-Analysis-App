"""Common agent interface.

Every agent — existing function-based ones and future class-based ones — plugs
into the app the same way: a ``name``, a ``description``, and a ``render()`` method
that draws its Streamlit UI and runs its interaction loop.

``FunctionAgent`` adapts the current ``*_app`` functions to this interface without
rewriting them (wrap any runtime arguments in a lambda at registration time), and
``AgentRegistry`` lets app.py build the sidebar/router by iterating registered
agents instead of maintaining a hand-written if/elif chain.
"""

from abc import ABC, abstractmethod
from typing import Callable, Dict, List


class BaseAgent(ABC):
    """Interface implemented by every agent."""

    name: str = ""
    description: str = ""

    @abstractmethod
    def render(self) -> None:
        """Render this agent's Streamlit UI and handle its interaction loop."""
        ...


class FunctionAgent(BaseAgent):
    """Adapts an existing agent function to :class:`BaseAgent`.

    ``render_fn`` must be a zero-argument callable; wrap agents that need runtime
    arguments (e.g. the Azure client or the current user id) in a lambda when you
    register them, so the registry stays uniform::

        registry.register(FunctionAgent(
            "DCF Ginny", "...",
            lambda: dcf_agent_app(client=openai_client, FMP_API_KEY=FMP_API_KEY),
        ))
    """

    def __init__(self, name: str, description: str, render_fn: Callable[[], None]):
        self.name = name
        self.description = description
        self._render_fn = render_fn

    def render(self) -> None:
        return self._render_fn()


class AgentRegistry:
    """Ordered collection of agents keyed by display name."""

    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> BaseAgent:
        if not agent.name:
            raise ValueError("Agent must have a non-empty name")
        self._agents[agent.name] = agent
        return agent

    def get(self, name: str):
        return self._agents.get(name)

    def names(self) -> List[str]:
        return list(self._agents.keys())

    def all(self) -> List[BaseAgent]:
        return list(self._agents.values())

    def __contains__(self, name: str) -> bool:
        return name in self._agents
