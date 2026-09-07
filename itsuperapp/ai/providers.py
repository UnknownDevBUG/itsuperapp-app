"""Provider-agnostic interface for the shared AI layer.

Concrete provider adapters (OpenAI, Anthropic, a self-hosted model, etc.)
implement this interface so LangGraph orchestration and Frappe callers never
depend on a specific vendor SDK directly. No adapter is implemented yet;
this is the scaffold contract only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
	"""Minimal contract every AI provider adapter must satisfy.

	Kept intentionally small for the scaffold stage. Extend with
	streaming, tool-calling, and structured-output methods once a real
	provider and use case are wired in (see GH-17 scope notes).
	"""

	name: str

	@abstractmethod
	def invoke(self, prompt: str, **kwargs: Any) -> str:
		"""Send a prompt to the underlying model and return its text
		response. Raises on provider/transport failure; callers decide
		retry/fallback policy."""
		raise NotImplementedError
