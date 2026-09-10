"""Model registry: where configured AI providers/models are looked up.

Domain modules resolve a model through this registry instead of
constructing a provider adapter directly, so provider/model configuration
stays centralized and swappable. No provider is registered yet; this is the
scaffold contract only, pending a verified AI provider policy (see
ARCHITECTURE.md "Deployment boundaries and open decisions").
"""

from __future__ import annotations

from itsuperapp.ai.providers import AIProvider, OpenRouterGeminiProvider

_REGISTRY: dict[str, AIProvider] = {}


def register_provider(key: str, provider: AIProvider) -> None:
	"""Register a configured provider instance under a lookup key."""
	_REGISTRY[key] = provider


def get_provider(key: str) -> AIProvider:
	"""Look up a registered provider by key.

	Raises KeyError if nothing has been registered yet -- callers should
	not silently fall back to an unconfigured default.
	"""
	return _REGISTRY[key]


def get_default_provider() -> AIProvider:
	"""Return the first real, non-scaffold provider: OpenRouter's Gemini.

	Lazily registers on first use rather than at module import time, so
	importing this module (e.g. from the api.py smoke test) never makes a
	network call or requires site config to be present. The instance itself
	reads its API key from site config lazily too, at `invoke()` time (see
	OpenRouterGeminiProvider._api_key), so registering here still does not
	require a key to be configured yet.
	"""
	try:
		return get_provider("openrouter_gemini")
	except KeyError:
		provider = OpenRouterGeminiProvider()
		register_provider("openrouter_gemini", provider)
		return provider
