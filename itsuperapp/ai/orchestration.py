"""Shared LangGraph orchestration primitives.

LangGraph owns AI workflow state, routing, retries, loops, and
human-in-the-loop AI steps (ADR 0002); Frappe Workflow continues to own
business/human approval workflow. This module holds only what is genuinely
reusable across domain AI workflows -- a common state shape and a factory
for an empty graph -- not any domain-specific graph, node, or prompt.

Scaffold only: verified end-to-end that `langgraph` imports cleanly inside
the Frappe bench Python environment (3.14.7) alongside `frappe` itself with
no dependency conflict. No domain workflow is wired in yet.
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import StateGraph


class AIWorkflowState(TypedDict, total=False):
	"""Common state shape shared AI workflows may extend.

	Kept minimal on purpose -- add fields only once a real workflow needs
	them, per SOUL.md's smallest-maintainable-solution guidance.
	"""

	input: str
	output: str


def new_workflow_graph() -> StateGraph:
	"""Return an empty StateGraph using the shared state shape.

	Domain modules add their own nodes/edges on top of this; this
	function does not compile or run anything by itself.
	"""
	return StateGraph(AIWorkflowState)
