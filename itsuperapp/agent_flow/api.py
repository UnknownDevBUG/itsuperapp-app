"""Whitelisted Agent Flow endpoints."""

from __future__ import annotations

from typing import Any

import frappe

from itsuperapp.agent_flow.node_registry import all_node_types
from itsuperapp.agent_flow.runtime import cancel_flow_run as _cancel_flow_run
from itsuperapp.agent_flow.runtime import resume_flow_run as _resume_flow_run
from itsuperapp.agent_flow.runtime import start_flow_run as _start_flow_run


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
