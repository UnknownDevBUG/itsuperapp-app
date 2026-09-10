"""Flow Definition DocType controller (issue #59).

The live, mutable node-graph a user edits in Studio (#60). Per
docs/architecture/agent-flow-design.md -> "Persistence Model": nodes/edges/
viewport/settings/schema_version. `validate()` implements the three named
checks from the design doc's Visual Layer table (mirroring FlowAgent's
`_validate_graph()` design); `on_update()` snapshots a new immutable
Flow Version whenever the graph content actually changed, deduped by
content hash.

See flow_version.py's module docstring for why every JSON-shaped field
here (nodes/edges/viewport/settings) is stored and passed around as an
explicit JSON string, parsed via `as_obj()` where the real structure is
needed, rather than a bare Python list.
"""

from __future__ import annotations

import frappe
from frappe.model.document import Document

from itsuperapp.itsuperapp.doctype.flow_version.flow_version import as_json, as_obj, compute_content_hash


class FlowDefinition(Document):
	def validate(self):
		self._normalize_json_fields()
		self._validate_non_empty_graph()
		self._validate_no_duplicate_node_ids()
		self._validate_no_unknown_edge_targets()

	def _normalize_json_fields(self):
		"""Ensure every JSON-shaped field is stored as a JSON string
		before Frappe's own DB-persistence layer sees it -- a bare list
		value fails there with "Value for X cannot be a list" for any
		non-table field, JSON fieldtype included."""
		self.nodes = as_json(self.nodes or [])
		self.edges = as_json(self.edges or [])
		self.viewport = as_json(self.viewport or {})
		self.settings = as_json(self.settings or {})

	def _validate_non_empty_graph(self):
		if not as_obj(self.nodes):
			frappe.throw(frappe._("A Flow Definition must contain at least one node."))

	def _validate_no_duplicate_node_ids(self):
		seen: set[str] = set()
		for node in as_obj(self.nodes) or []:
			node_id = node.get("id")
			if node_id in seen:
				frappe.throw(frappe._("Duplicate node id in graph: {0}").format(node_id))
			seen.add(node_id)

	def _validate_no_unknown_edge_targets(self):
		node_ids = {node.get("id") for node in as_obj(self.nodes) or []}
		for edge in as_obj(self.edges) or []:
			for endpoint_field in ("source", "target"):
				endpoint = edge.get(endpoint_field)
				if endpoint not in node_ids:
					frappe.throw(
						frappe._("Edge {0} references unknown node id: {1}").format(edge.get("id"), endpoint)
					)

	def on_update(self):
		self.maybe_snapshot_version()

	def maybe_snapshot_version(self, label: str | None = None) -> str | None:
		"""Create a new Flow Version snapshot unless the content is
		identical to the most recent existing snapshot for this
		Flow Definition (content-hash dedupe). Returns the new Flow
		Version's name, or None if no new snapshot was needed.
		"""
		content_hash = compute_content_hash(self.nodes, self.edges, self.viewport, self.settings)
		existing = frappe.db.exists(
			"Flow Version",
			{"flow_definition": self.name, "content_hash": content_hash},
		)
		if existing:
			return None
		version = frappe.new_doc("Flow Version")
		version.flow_definition = self.name
		version.label = label or ""
		version.creator = frappe.session.user
		version.content_hash = content_hash
		version.nodes = self.nodes
		version.edges = self.edges
		version.viewport = self.viewport
		version.settings = self.settings
		version.insert(ignore_permissions=False)
		return version.name
