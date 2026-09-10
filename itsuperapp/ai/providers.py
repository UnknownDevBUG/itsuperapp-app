"""Provider-agnostic interface for the shared AI layer.

Concrete provider adapters (OpenAI, Anthropic, a self-hosted model, etc.)
implement this interface so LangGraph orchestration and Frappe callers never
depend on a specific vendor SDK directly. No adapter is implemented yet;
this is the scaffold contract only.
"""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from typing import Any

import frappe
import requests


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


class OpenRouterGeminiProvider(AIProvider):
	"""First concrete adapter: Gemini via OpenRouter's OpenAI-compatible API.

	Per Sprint 1 week plan (Roadmap Issue #28, Thursday 10 Sep): Document AI
	backend needs a real provider call, not another scaffold layer. OpenRouter
	is used instead of calling Google's Gemini API directly so the provider
	can be swapped later (per ADR 0002's provider-agnostic goal) without
	touching call sites -- only this class and the site config key change.

	The API key is read from Frappe site config (`itsuperapp_openrouter_api_key`)
	via `frappe.conf`, never hardcoded or passed by the caller -- this follows
	the same pattern as `itsuperapp_supabase_db_host`/`_port` in api.py.
	Raises `frappe.ValidationError` at call time (not import time) if the key
	is missing, so importing this module stays side-effect-free.
	"""

	name = "openrouter_gemini"

	API_URL = "https://openrouter.ai/api/v1/chat/completions"
	# Model is a site-config override (`itsuperapp_openrouter_model`), not a
	# hardcoded constant, since OpenRouter model slugs/availability change
	# over time and this may need to move to a paid tier once quota is hit.
	DEFAULT_MODEL = "google/gemini-2.0-flash-exp:free"

	def __init__(self, timeout: int = 60) -> None:
		self.timeout = timeout

	def _api_key(self) -> str:
		api_key = frappe.conf.get("itsuperapp_openrouter_api_key")
		if not api_key:
			frappe.throw(
				"itsuperapp_openrouter_api_key is not set in site config. "
				"Run: bench --site <site> set-config itsuperapp_openrouter_api_key <key>"
			)
		return api_key

	def invoke(
		self,
		prompt: str,
		*,
		file_bytes: bytes | None = None,
		mime_type: str | None = None,
		**kwargs: Any,
	) -> str:
		"""Send a prompt to Gemini via OpenRouter and return the text reply.

		`file_bytes`/`mime_type` attach a document/image as an OpenAI-style
		`image_url` data URI content block alongside the text prompt -- this
		is how OpenRouter's chat/completions endpoint accepts multimodal
		input for vision-capable models like Gemini, there is no separate
		upload step. Both must be provided together or not at all.
		"""
		if bool(file_bytes) != bool(mime_type):
			raise ValueError("file_bytes and mime_type must be provided together")

		content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
		if file_bytes is not None:
			encoded = base64.b64encode(file_bytes).decode("ascii")
			content.append(
				{
					"type": "image_url",
					"image_url": {"url": f"data:{mime_type};base64,{encoded}"},
				}
			)

		model = frappe.conf.get("itsuperapp_openrouter_model") or self.DEFAULT_MODEL
		response = requests.post(
			self.API_URL,
			headers={
				"Authorization": f"Bearer {self._api_key()}",
				"Content-Type": "application/json",
			},
			json={
				"model": model,
				"messages": [{"role": "user", "content": content}],
			},
			timeout=self.timeout,
		)
		response.raise_for_status()
		data = response.json()
		try:
			return data["choices"][0]["message"]["content"]
		except (KeyError, IndexError) as exc:
			raise RuntimeError(f"Unexpected OpenRouter response shape: {data}") from exc
