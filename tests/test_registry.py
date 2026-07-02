"""AgentRegistry / FunctionAgent — the router's dispatch primitives."""

import pytest

from agents.base import AgentRegistry, BaseAgent, FunctionAgent


def test_dispatch_and_lookup():
    calls = []
    reg = AgentRegistry()
    agent = FunctionAgent("DCF Ginny", "A DCF agent", lambda: calls.append("ran"))
    reg.register(agent)

    assert isinstance(agent, BaseAgent)
    assert "DCF Ginny" in reg
    assert reg.get("DCF Ginny") is agent
    assert reg.get("Unknown Agent") is None      # -> app.py falls through to Welcome page
    assert reg.names() == ["DCF Ginny"]
    assert reg.all() == [agent]

    reg.get("DCF Ginny").render()
    assert calls == ["ran"]


def test_registration_does_not_run_agent():
    calls = []
    reg = AgentRegistry()
    reg.register(FunctionAgent("X", "d", lambda: calls.append(1)))
    assert calls == []                            # building the registry must not render
    reg.get("X").render()
    assert calls == [1]


def test_empty_name_rejected():
    with pytest.raises(ValueError):
        AgentRegistry().register(FunctionAgent("", "d", lambda: None))


def test_title_attribute_roundtrips():
    # app.py sets `.title` on each FunctionAgent for the welcome cards.
    agent = FunctionAgent("Name", "Desc", lambda: None)
    agent.title = "📈 Name"
    assert agent.title == "📈 Name"
    assert agent.description == "Desc"
