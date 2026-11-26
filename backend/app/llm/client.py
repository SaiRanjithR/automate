"""LLM access. Every model call in the app goes through `get_llm(settings).complete(...)`.

Two providers share one interface:
- AnthropicLLM: Claude via the Anthropic SDK with structured outputs (`messages.parse`).
- OfflineLLM: deterministic rule-based fallback, used when no API key is configured and in tests.
"""

import json
import logging
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.core.errors import LLMError

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)
PROMPTS_DIR = Path(__file__).parent / "prompts"


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    system: str
    user: str

    def render_user(self, variables: dict[str, Any]) -> str:
        text = self.user
        for key, value in variables.items():
            rendered = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            text = text.replace("{{" + key + "}}", rendered)
        return text

    def render_system(self, variables: dict[str, Any]) -> str:
        text = self.system
        for key, value in variables.items():
            if isinstance(value, str | int | float):
                text = text.replace("{{" + key + "}}", str(value))
        return text


@lru_cache(maxsize=32)
def load_prompt(name: str) -> Prompt:
    raw = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    header, _, rest = raw.partition("---system---")
    system, _, user = rest.partition("---user---")
    version = "0"
    for line in header.splitlines():
        if line.startswith("version:"):
            version = line.split(":", 1)[1].strip()
    return Prompt(name=name, version=f"{name}@{version}", system=system.strip(), user=user.strip())


class UsageMeter:
    """Thread-safe token counter with a hard cap (per project)."""

    def __init__(self, cap: int, already_used: int = 0) -> None:
        self.cap = cap
        self.used = already_used
        self._lock = threading.Lock()

    def add(self, tokens: int) -> None:
        with self._lock:
            self.used += tokens
            if self.used > self.cap:
                raise LLMError(
                    f"Token budget for this project exceeded ({self.used:,} > {self.cap:,}). "
                    "Raise LLM_MAX_TOKENS_PER_PROJECT to continue."
                )


@dataclass(frozen=True)
class LLMResult[T: BaseModel]:
    value: T
    prompt_version: str
    model: str


class LLM(Protocol):
    name: str

    def complete(
        self,
        prompt_name: str,
        variables: dict[str, Any],
        schema: type[T],
        usage: UsageMeter | None = None,
    ) -> LLMResult[T]: ...


class AnthropicLLM:
    """Claude via the Anthropic SDK. Structured outputs guarantee schema-valid JSON."""

    FALLBACK_BETA = "server-side-fallback-2026-07-01"

    def __init__(self, settings: Settings) -> None:
        import anthropic

        if settings.anthropic_api_key is None:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        self._anthropic = anthropic
        self._client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            timeout=float(settings.llm_timeout_seconds),
            max_retries=3,
        )
        self.model = settings.llm_model
        self.effort = settings.llm_effort
        self.name = f"anthropic:{self.model}"

    def complete(
        self,
        prompt_name: str,
        variables: dict[str, Any],
        schema: type[T],
        usage: UsageMeter | None = None,
    ) -> LLMResult[T]:
        prompt = load_prompt(prompt_name)
        system = prompt.render_system(variables)
        user = prompt.render_user(variables)
        last_error = ""
        for attempt in range(2):
            content = (
                user if attempt == 0 else f"{user}\n\nYour previous reply was invalid: {last_error}"
            )
            response = self._call(system, content, schema)
            if usage is not None:
                usage.add(response.usage.input_tokens + response.usage.output_tokens)
            if response.stop_reason == "refusal":
                raise LLMError(f"The model declined the {prompt_name} request")
            if response.stop_reason == "max_tokens":
                last_error = "the reply was cut off at max_tokens; be more concise"
                continue
            parsed = response.parsed_output
            if parsed is None:
                last_error = "no structured output was returned"
                continue
            try:
                value = schema.model_validate(parsed.model_dump())
            except ValidationError as exc:
                last_error = str(exc)[:500]
                continue
            logger.info(
                "LLM %s ok (model=%s, in=%s, out=%s)",
                prompt.version,
                response.model,
                response.usage.input_tokens,
                response.usage.output_tokens,
            )
            return LLMResult(value=value, prompt_version=prompt.version, model=response.model)
        raise LLMError(f"{prompt_name}: invalid model output after retry ({last_error})")

    def _call(self, system: str, user: str, schema: type[T]) -> Any:
        anthropic = self._anthropic
        try:
            return self._client.beta.messages.parse(
                model=self.model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=schema,
                output_config={"effort": self.effort},
                betas=[self.FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.AuthenticationError as exc:
            raise LLMError("The Anthropic API key was rejected") from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("Rate limited by the Anthropic API; try again shortly") from exc
        except anthropic.BadRequestError as exc:
            raise LLMError(f"Anthropic API rejected the request: {exc.message}") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Anthropic API error {exc.status_code}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("Could not reach the Anthropic API") from exc


def get_llm(settings: Settings) -> LLM:
    if settings.effective_llm_provider == "anthropic":
        return AnthropicLLM(settings)
    from app.llm.offline import OfflineLLM

    return OfflineLLM()
