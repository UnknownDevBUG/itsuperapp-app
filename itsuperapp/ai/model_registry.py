"""Model registry: where configured AI providers/models are looked up.

Domain modules resolve a model through this registry instead of
constructing a provider adapter directly, so provider/model configuration
stays centralized and swappable. No provider is registered yet; this is the
scaffold contract only, pending a verified AI provider policy (see
ARCHITECTURE.md "Deployment boundaries and open decisions").
"""

from __future__ import annotations

from itsuperapp.ai.providers import AIProvider

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
