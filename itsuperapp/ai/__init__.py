"""Shared AI layer: provider interfaces, model registry, and orchestration
primitives.

This package owns the parts of the Frappe -> LangChain -> LangGraph -> AI
provider boundary (see ARCHITECTURE.md and ADR 0002) that are genuinely
reusable across domains: a provider-agnostic interface, a place to register
configured models, and any shared LangGraph orchestration primitives.

It intentionally holds no domain-specific prompts, extraction logic, or
business agents. A domain module (e.g. Document AI) owns its own AI
subpackage that depends on this shared layer, not the other way around,
per the "Module Boundaries and Dependency Direction" section of
.agents/taro/SOUL.md.

Scaffold only: no provider is wired to a live API key or Frappe endpoint
yet. See GH-17 for scope and GH-1 for the parent foundation tracking issue.
"""
