"""Unified LLM client.

A thin wrapper so agents make model calls through one API instead of each
hand-rolling ``http_post``/SDK calls. It deliberately mirrors the request/response
shapes already used across the agents so adopting it is a drop-in replacement:

    from llm import llm

    text = llm.complete("Summarise this filing", system="You are an analyst.")
    text = llm.complete(prompt, provider="azure", temperature=0.2)
    text = llm.chat(messages, provider="deepseek")   # when you already have messages

Providers:
- ``"deepseek"`` (default): POST to the DeepSeek chat-completions endpoint via the
  shared retrying HTTP session (utils.net.http_post).
- ``"azure"``: the shared Azure OpenAI client (config.get_azure_client()).
- ``"openai"``: the public OpenAI API (requires OPENAI_API_KEY).

Google Vertex/Gemini (used only by the PE agent) is intentionally out of scope for
now; that agent keeps its bespoke client until it is migrated.
"""

import config
from utils.net import http_post

DEEPSEEK_MODEL = "deepseek-chat"


class LLMClient:
    """Provider-agnostic chat/completion helper returning the response text."""

    def __init__(self, default_provider: str = "deepseek"):
        self.default_provider = default_provider

    # -- public API -----------------------------------------------------------
    def complete(self, prompt: str, system: str = None, provider: str = None, **kwargs) -> str:
        """Single-prompt convenience wrapper. Builds the messages list and calls chat()."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, provider=provider, **kwargs)

    def chat(self, messages, provider: str = None, temperature: float = 0.3,
             max_tokens: int = None, model: str = None, **kwargs) -> str:
        """Run a chat completion for a pre-built messages list; returns the reply text."""
        provider = (provider or self.default_provider).lower()
        if provider == "deepseek":
            return self._deepseek(messages, temperature, max_tokens, model, **kwargs)
        if provider in ("azure", "azure_openai"):
            return self._azure(messages, temperature, max_tokens, model, **kwargs)
        if provider == "openai":
            return self._openai(messages, temperature, max_tokens, model, **kwargs)
        raise ValueError(f"Unknown LLM provider: {provider!r}")

    # -- providers ------------------------------------------------------------
    def _deepseek(self, messages, temperature, max_tokens, model, timeout=None, **kwargs):
        payload = {
            "model": model or DEEPSEEK_MODEL,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        payload.update(kwargs)
        post_kwargs = {
            "headers": {"Authorization": f"Bearer {config.DEEPSEEK_API_KEY}"},
            "json": payload,
        }
        if timeout is not None:
            post_kwargs["timeout"] = timeout
        response = http_post(config.DEEPSEEK_API_URL, **post_kwargs)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def _azure(self, messages, temperature, max_tokens, model, **kwargs):
        client = config.get_azure_client()
        response = client.chat.completions.create(
            model=model or config.AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        return response.choices[0].message.content

    def _openai(self, messages, temperature, max_tokens, model, **kwargs):
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=model or "gpt-4o-mini",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        return response.choices[0].message.content


# Shared default instance for convenient imports: ``from llm import llm``
llm = LLMClient()
