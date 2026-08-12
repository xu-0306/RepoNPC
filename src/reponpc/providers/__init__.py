"""RepoNPC-owned model provider adapters and capability boundaries."""

from reponpc.providers.contracts import (
    ChatProvider,
    ProviderCapabilities,
    ProviderError,
    ProviderFailureCode,
    ProviderHealth,
    ProviderMessage,
    ProviderResult,
    ProviderUsage,
    ResponseSchema,
    RuntimeEmbeddingProvider,
)
from reponpc.providers.ollama import OllamaChatProvider
from reponpc.providers.ollama_embeddings import OllamaEmbeddingProvider
from reponpc.providers.openai_compatible import OpenAICompatibleChatProvider
from reponpc.providers.openai_embeddings import OpenAICompatibleEmbeddingProvider

__all__ = [
    "ChatProvider",
    "OllamaChatProvider",
    "OllamaEmbeddingProvider",
    "OpenAICompatibleChatProvider",
    "OpenAICompatibleEmbeddingProvider",
    "ProviderCapabilities",
    "ProviderError",
    "ProviderFailureCode",
    "ProviderHealth",
    "ProviderMessage",
    "ProviderResult",
    "ProviderUsage",
    "ResponseSchema",
    "RuntimeEmbeddingProvider",
]
