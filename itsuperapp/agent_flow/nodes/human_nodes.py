"""Human node executors (issue #50).

Human Approval's actual pause/token/notification/resume mechanics live in
`itsuperapp.agent_flow.runtime` (`NodeWaiting`'s approval fields,
`resume_flow_run_with_token`) -- centralized there rather than
reimplemented per node, matching this design's single-centralized-
mechanism principle already established for permissions/registry. This
executor's only job is to request that pause with the right metadata.
"""

from __future__ import annotations

from typing import Any

from itsuperapp.agent_flow.node_registry import node
from itsuperapp.agent_flow.runtime import NodeWaiting


@node(
	"human_approval",
	label="Human Approval",
	description=(
		"Pauses the run (Waiting) until the configured approver resumes it via a secure, "
		"single-use resume token delivered through Frappe's native Notification Log."
	),
	category="Human",
	inputs=[{"name": "in", "multiple": False}],
	outputs=[{"name": "out"}],
	config_schema=[
		{"name": "approver", "label": "Approver (User)", "type": "Data"},
		{"name": "subject", "label": "Notification Subject", "type": "Data"},
	],
)
class HumanApprovalNode:
	@staticmethod
	def execute(context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
		raise NodeWaiting(approver=config["approver"], subject=config.get("subject"))
