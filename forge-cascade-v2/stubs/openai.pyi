"""Type stubs for OpenAI Python SDK."""
from typing import Any, Sequence


class ChatCompletionMessage:
    content: str | None
    role: str


class Choice:
    message: ChatCompletionMessage
    index: int
    finish_reason: str | None


class ChatCompletion:
    id: str
    choices: list[Choice]
    created: int
    model: str


class CompletionsResource:
    async def create(
        self,
        *,
        model: str,
        messages: Sequence[dict[str, Any]],
        temperature: float = ...,
        max_tokens: int | None = ...,
        **kwargs: Any,
    ) -> ChatCompletion: ...


class ChatResource:
    completions: CompletionsResource


class EmbeddingData:
    embedding: list[float]
    index: int


class EmbeddingsResponse:
    data: list[EmbeddingData]
    model: str


class EmbeddingsResource:
    async def create(
        self,
        *,
        input: str | list[str],
        model: str,
        dimensions: int | None = ...,
        **kwargs: Any,
    ) -> EmbeddingsResponse: ...


class AsyncOpenAI:
    def __init__(
        self,
        *,
        api_key: str | None = ...,
        organization: str | None = ...,
        base_url: str | None = ...,
        timeout: float | None = ...,
        **kwargs: Any,
    ) -> None: ...

    chat: ChatResource
    embeddings: EmbeddingsResource


class OpenAI:
    def __init__(
        self,
        *,
        api_key: str | None = ...,
        organization: str | None = ...,
        base_url: str | None = ...,
        timeout: float | None = ...,
        **kwargs: Any,
    ) -> None: ...

    chat: ChatResource
    embeddings: EmbeddingsResource
