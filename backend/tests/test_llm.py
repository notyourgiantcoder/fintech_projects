import openai
import pytest
from agent_framework.exceptions import ChatClientException

from finbo.llm import (
    AllProvidersFailedError,
    ConfiguredProvider,
    NoProviderConfiguredError,
    Provider,
    configured_providers,
    is_provider_failure,
    run_with_fallback,
)


def rate_limit() -> openai.RateLimitError:
    # Built without a transport response: only the exception type matters here.
    err = openai.RateLimitError.__new__(openai.RateLimitError)
    Exception.__init__(err, "Error code: 429 - Rate limit reached")
    return err


def wrapped(exc: BaseException) -> RuntimeError:
    try:
        raise RuntimeError("framework wrapper") from exc
    except RuntimeError as w:
        return w


class FakeAgent:
    def __init__(self, outcome):
        self.outcome = outcome

    async def run(self, prompt):
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def provider(name: str, outcome) -> ConfiguredProvider:
    p = Provider(name, "https://example.test", f"{name.upper()}_KEY", f"{name.upper()}_MODEL", "m")
    return ConfiguredProvider(provider=p, model="m", client=outcome)  # client carries the outcome


def build(client):
    return FakeAgent(client)


def test_detects_provider_errors_through_wrappers():
    assert is_provider_failure(rate_limit())
    assert is_provider_failure(wrapped(rate_limit()))
    assert is_provider_failure(ChatClientException("service unavailable"))
    assert not is_provider_failure(ValueError("bug in our code"))


async def test_falls_back_on_rate_limit():
    result = await run_with_fallback(
        build, "q", [provider("github", wrapped(rate_limit())), provider("gemini", "answer")]
    )
    assert (result.provider, result.response) == ("gemini", "answer")
    assert len(result.failures) == 1 and result.failures[0].startswith("github")


async def test_does_not_mask_our_own_bugs():
    with pytest.raises(ValueError):
        await run_with_fallback(
            build, "q", [provider("github", ValueError("bug")), provider("gemini", "answer")]
        )


async def test_all_providers_failing():
    with pytest.raises(AllProvidersFailedError) as info:
        await run_with_fallback(
            build, "q", [provider("github", rate_limit()), provider("gemini", rate_limit())]
        )
    assert len(info.value.failures) == 2


def test_provider_selection_from_env(monkeypatch):
    for var in ("GITHUB_TOKEN", "GOOGLE_API_KEY", "GITHUB_MODEL", "GEMINI_MODEL"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(NoProviderConfiguredError):
        configured_providers()

    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    (only,) = configured_providers()
    assert (only.provider.name, only.model) == ("gemini", "gemini-2.5-flash")

    monkeypatch.setenv("GEMINI_MODEL", "gemini-custom")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    assert [(c.provider.name, c.model) for c in configured_providers()] == [
        ("github", "openai/gpt-4.1-mini"),
        ("gemini", "gemini-custom"),
    ]
    with pytest.raises(NoProviderConfiguredError):
        monkeypatch.delenv("GITHUB_TOKEN")
        configured_providers(only="github")
