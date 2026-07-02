"""LLM access layer.

Exposes a single ``LLMClient`` that wraps the providers used across the app
(DeepSeek, Azure OpenAI, OpenAI) behind one ``complete`` / ``chat`` API, plus a
ready-to-use module-level ``llm`` singleton.
"""

from llm.client import LLMClient, llm

__all__ = ["LLMClient", "llm"]
