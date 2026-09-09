"""Whitelisted Agent Flow endpoints."""

from __future__ import annotations

from typing import Any

import frappe

from itsuperapp.agent_flow.node_registry import all_node_types


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
