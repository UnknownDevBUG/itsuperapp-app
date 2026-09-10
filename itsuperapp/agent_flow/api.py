"""Whitelisted Agent Flow endpoints."""

from __future__ import annotations

from typing import Any

import frappe

from itsuperapp.agent_flow.node_registry import all_node_types
from itsuperapp.agent_flow.runtime import cancel_flow_run as _cancel_flow_run
from itsuperapp.agent_flow.runtime import resume_flow_run as _resume_flow_run
from itsuperapp.agent_flow.runtime import resume_flow_run_with_token as _resume_flow_run_with_token
from itsuperapp.agent_flow.runtime import start_flow_run as _start_flow_run
from itsuperapp.agent_flow.triggers import webhook_endpoint as _webhook_endpoint


@frappe.whitelist()
def get_node_registry() -> list[dict[str, Any]]:
	"""Return every registered node type's metadata.

	The Node Metadata API per docs/architecture/agent-flow-design.md --
	Studio's palette and properties panel must render from this response
	only, never a hand-copied list. Returns structured metadata only
	(type/version/label/description/category/icon/inputs/outputs/
	config_schema/permissions/capabilities); no secret or runtime-sensitive
	data is present in a node's registered metadata.
	"""
	return list(all_node_types().values())


@frappe.whitelist()
def start_flow_run(flow_definition: str, config: dict | str | None = None) -> str:
	"""Manual Run API (issue #48) -- see runtime.start_flow_run. Enqueues
	execution and returns the new Flow Run's name immediately; never runs
	the workflow synchronously inside this HTTP request."""
	return _start_flow_run(flow_definition=flow_definition, config=config)


@frappe.whitelist()
def resume_flow_run(run_name: str) -> None:
	"""Resume a Waiting Flow Run (issue #48) -- see runtime.resume_flow_run."""
	_resume_flow_run(run_name)


@frappe.whitelist()
def cancel_flow_run(run_name: str) -> None:
	"""Cancel a Flow Run (issue #48) -- see runtime.cancel_flow_run."""
	_cancel_flow_run(run_name)


@frappe.whitelist(allow_guest=False)
def resume_flow_run_with_token(run_name: str, token: str) -> None:
	"""Resume a Human Approval Waiting Flow Run via its resume token
	(issue #50) -- see runtime.resume_flow_run_with_token. Requires an
	authenticated (non-Guest) session; the token itself, not the caller's
	own roles, authorizes this specific resume."""
	_resume_flow_run_with_token(run_name, token)


@frappe.whitelist()
def create_flow_definition(flow_name: str) -> str:
	"""Create a new Flow Definition for Studio's "create new" picker
	(issue #60), seeded with a single `noop` node -- Flow Definition's own
	validate() (issue #59) requires a non-empty graph, so an entirely
	empty flow cannot be saved; this is the minimal graph that satisfies
	it, not a Studio-side relaxation of that server-side rule."""
	doc = frappe.new_doc("Flow Definition")
	doc.flow_name = flow_name
	doc.schema_version = 1
	doc.nodes = [{"id": "n1", "type": "noop", "position": {"x": 100, "y": 100}, "config": {}}]
	doc.edges = []
	doc.viewport = {"x": 0, "y": 0, "zoom": 1}
	doc.settings = {}
	doc.insert()
	return doc.name


@frappe.whitelist(allow_guest=True, methods=["POST"])
def webhook_endpoint(trigger_key: str | None = None) -> dict[str, Any]:
	"""Inbound Agent Flow webhook trigger (issue #62) -- see
	triggers.webhook_endpoint. `allow_guest=True` only lets the HTTP layer
	reach this method without a login session; every request must still
	pass real HMAC-SHA256 verification (X-Agent-Flow-Timestamp/
	X-Agent-Flow-Signature headers) or is rejected before anything is
	enqueued."""
	return _webhook_endpoint(trigger_key=trigger_key)
