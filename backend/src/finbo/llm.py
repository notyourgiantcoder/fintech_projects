"""LLM providers (free tiers) with automatic fallback.

GitHub Models is primary; Gemini is the fallback when GitHub's daily limit is hit.
Both expose OpenAI-compatible chat-completions endpoints, so one client type serves both.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import openai
from agent_framework.exceptions import ChatClientException
from agent_framework.openai import OpenAIChatCompletionClient
from dotenv import find_dotenv, load_dotenv


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    key_env: str
    model_env: str
    default_model: str


PROVIDERS: tuple[Provider, ...] = (
    Provider(
        name="github",
        base_url="https://models.github.ai/inference",
        key_env="GITHUB_TOKEN",
        model_env="GITHUB_MODEL",
        default_model="openai/gpt-4.1-mini",
    ),
    Provider(
        name="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        key_env="GOOGLE_API_KEY",
        model_env="GEMINI_MODEL",
        default_model="gemini-2.5-flash",
    ),
)


class NoProviderConfiguredError(RuntimeError):
    pass


class AllProvidersFailedError(RuntimeError):
    def __init__(self, failures: Sequence[str]):
        super().__init__("All LLM providers failed:\n  " + "\n  ".join(failures))
        self.failures = list(failures)


@dataclass
class ConfiguredProvider:
    provider: Provider
    model: str
    client: OpenAIChatCompletionClient


def load_env() -> None:
    """Load the repo-root .env (searched upward from the current directory)."""
    load_dotenv(find_dotenv(usecwd=True))


def configured_providers(only: str | None = None) -> list[ConfiguredProvider]:
    result = []
    for p in PROVIDERS:
        if only and p.name != only:
            continue
        key = os.getenv(p.key_env)
        if not key:
            continue
        model = os.getenv(p.model_env) or p.default_model
        client = OpenAIChatCompletionClient(model=model, api_key=key, base_url=p.base_url)
        result.append(ConfiguredProvider(provider=p, model=model, client=client))
    if not result:
        wanted = [p.key_env for p in PROVIDERS if not only or p.name == only]
        raise NoProviderConfiguredError(
            f"No LLM key found. Set {' or '.join(wanted)} in .env (see .env.example)."
        )
    return result


def is_provider_failure(exc: BaseException) -> bool:
    """True for errors from the LLM service itself (rate limit, auth, outage, bad model)."""
    seen: BaseException | None = exc
    while seen is not None:
        if isinstance(seen, openai.APIError | ChatClientException):
            return True
        seen = seen.__cause__ or seen.__context__
    return False


class SupportsRun(Protocol):
    def run(self, messages: Any = None, **kwargs: Any) -> Awaitable[Any]: ...


@dataclass
class FallbackResult:
    provider: str
    model: str
    response: Any
    failures: list[str] = field(default_factory=list)


async def run_with_fallback(
    build_agent: Callable[[OpenAIChatCompletionClient], SupportsRun],
    prompt: Any,
    providers: Sequence[ConfiguredProvider],
) -> FallbackResult:
    """Run on each provider in turn until one succeeds.

    A failed attempt is retried from scratch on the next provider. That is safe while
    agent tools are read-only; tools with side effects must be idempotent or gated by
    human approval before they are added.
    """
    failures: list[str] = []
    for cp in providers:
        try:
            response = await build_agent(cp.client).run(prompt)
        except Exception as e:
            if not is_provider_failure(e):
                raise
            failures.append(f"{cp.provider.name} ({cp.model}): {str(e).splitlines()[0][:200]}")
            continue
        return FallbackResult(cp.provider.name, cp.model, response, failures)
    raise AllProvidersFailedError(failures)
