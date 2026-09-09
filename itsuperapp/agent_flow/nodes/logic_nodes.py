"""Logic node executors (issue #50).

Condition/branch evaluation is deterministic and never arbitrary `eval`/
`exec`: `left`/`right` values may reference the run's context via
Frappe's own sandboxed Jinja (`frappe.render_template`, the same trust
boundary Server Scripts and this design's other templated fields already
use), and the comparison itself is restricted to a small, fixed operator
table -- never a user-supplied Python expression string.
"""

from __future__ import annotations

import operator
from typing import Any

import frappe

from itsuperapp.agent_flow.node_registry import node

_OPERATORS = {
	"==": operator.eq,
	"!=": operator.ne,
	">": operator.gt,
	"<": operator.lt,
	">=": operator.ge,
	"<=": operator.le,
	"in": lambda a, b: a in b,
	"not in": lambda a, b: a not in b,
}


def _render(value: Any, context: dict[str, Any]) -> Any:
	"""Render a `{{ ... }}` placeholder against the run context via
	Frappe's sandboxed Jinja, or return non-string values unchanged."""
	if isinstance(value, str) and "{{" in value:
		return frappe.render_template(value, context)
	return value


@node(
	"logic_condition",
	label="Condition",
	description="Evaluates left <op> right (safe, fixed operator set) and routes to out-yes/out-no.",
	category="Logic",
	inputs=[{"name": "in", "multiple": False}],
	outputs=[{"name": "out-yes"}, {"name": "out-no"}],
	config_schema=[
		{"name": "left", "label": "Left value (supports {{ }})", "type": "Data"},
		{"name": "operator", "label": "Operator", "type": "Select", "options": list(_OPERATORS.keys())},
		{"name": "right", "label": "Right value (supports {{ }})", "type": "Data"},
	],
)
class LogicConditionNode:
	@staticmethod
	def execute(context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
		op_name = config.get("operator")
		compare = _OPERATORS.get(op_name)
		if compare is None:
			frappe.throw(
				frappe._("Unknown Condition operator: {0}. Allowed: {1}").format(
					op_name, ", ".join(_OPERATORS)
				)
			)
		left = _render(config.get("left"), context)
		right = _render(config.get("right"), context)
		port = "out-yes" if compare(left, right) else "out-no"
		return {"context": context, "port": port}
