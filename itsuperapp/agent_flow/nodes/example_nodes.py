"""Trivial example node executors (registry proof only, see nodes/__init__.py).

Registered by default via the `agent_flow_nodes` hook in this app's
hooks.py -- proof that hook-based loading populates the registry, not a
statement that `noop`/`set_variable` are real, supported node types for
end users.
"""

from __future__ import annotations

from typing import Any

from itsuperapp.agent_flow.node_registry import node


@node(
	"noop",
	label="No-op",
	description="Does nothing; passes its input through unchanged.",
	category="Logic",
	inputs=[{"name": "in", "multiple": False}],
	outputs=[{"name": "out"}],
	config_schema=[],
	capabilities=[],
)
class NoopNode:
	"""Executor stub: no runtime engine exists yet (issue #48)."""

	@staticmethod
	def execute(context: dict[str, Any]) -> dict[str, Any]:
		return context


@node(
	"set_variable",
	label="Set Variable",
	description="Sets a named variable in the run context to a fixed value.",
	category="Data",
	inputs=[{"name": "in", "multiple": False}],
	outputs=[{"name": "out"}],
	config_schema=[
		{"name": "variable_name", "label": "Variable Name", "type": "Data"},
		{"name": "value", "label": "Value", "type": "Data"},
	],
	capabilities=[],
)
class SetVariableNode:
	"""Executor stub: no runtime engine exists yet (issue #48)."""

	@staticmethod
	def execute(context: dict[str, Any]) -> dict[str, Any]:
		return context
