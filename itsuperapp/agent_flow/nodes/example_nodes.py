"""Trivial example node executors (registry proof only, see nodes/__init__.py).

Registered by default via the `agent_flow_nodes` hook in this app's
hooks.py -- proof that hook-based loading populates the registry, not a
statement that `noop`/`set_variable` are real, supported node types for
end users.

Executor contract (issue #48): `execute(context, config)` returns
`{"context": <dict>, "port": <str, default "out">}`, may raise
`itsuperapp.agent_flow.runtime.NodeWaiting` to pause the run, or raise
any other exception to signal failure (subject to the run's retry/
on_error policy). These two nodes were left as passthrough stubs by
issue #61 specifically for #48 to complete this contract against.
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
	@staticmethod
	def execute(context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
		return {"context": context, "port": "out"}


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
	@staticmethod
	def execute(context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
		new_context = dict(context)
		variable_name = config.get("variable_name")
		if variable_name:
			new_context[variable_name] = config.get("value")
		return {"context": new_context, "port": "out"}
