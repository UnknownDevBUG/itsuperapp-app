"""Core Frappe/ERPNext node executors (issue #50).

Every node here drives existing Frappe capability through its standard,
permission-checked public API -- never `ignore_permissions=True`, never
unchecked `frappe.get_all` for a user-sensitive read, never a raw-SQL
bypass, never a parallel assignment/notification/workflow engine.

Security note: these executors do NOT call `authorize_node_operation()`
themselves -- the runtime (`itsuperapp.agent_flow.runtime`) already calls
it, once, before resolving/invoking any executor (issue #49's centralized
gate). What each node does here is the *second* half of the contract:
having passed the gate, actually perform its Frappe operation through a
real permission-checked API (not `ignore_permissions`), so a node can
never use a passed gate check as an excuse to skip Frappe's own
document-level permission enforcement too. `frappe.session.user` is
already the resolved execution identity by this point (the runtime calls
`frappe.set_user()` before executing any node), so every API below that
implicitly reads `frappe.session.user` (e.g. `apply_workflow`,
`Document.insert/save/submit`) is checking the *execution identity*, not
a caller's or Administrator's session.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.desk.form.assign_to import add as assign_to_add
from frappe.model.workflow import apply_workflow

from itsuperapp.agent_flow.node_registry import node

_DOC_FIELDS_CONFIG_SCHEMA = [
	{"name": "doctype", "label": "Document Type", "type": "Data"},
	{"name": "values", "label": "Field Values (JSON object)", "type": "JSON"},
]


@node(
	"frappe_create_document",
	label="Create Document",
	description="Creates a new Frappe document via the standard, permission-checked Document API.",
	category="Frappe",
	inputs=[{"name": "in", "multiple": False}],
	outputs=[{"name": "out"}],
	config_schema=_DOC_FIELDS_CONFIG_SCHEMA,
	allowed_operations=["create"],
)
class FrappeCreateDocumentNode:
	@staticmethod
	def execute(context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
		values = dict(config.get("values") or {})
		values["doctype"] = config["doctype"]
		doc = frappe.get_doc(values)
		doc.insert()
		new_context = dict(context)
		new_context["last_document"] = {"doctype": doc.doctype, "name": doc.name}
		return {"context": new_context, "port": "out"}


@node(
	"frappe_update_document",
	label="Update Document",
	description="Updates an existing Frappe document via the standard, permission-checked Document API.",
	category="Frappe",
	inputs=[{"name": "in", "multiple": False}],
	outputs=[{"name": "out"}],
	config_schema=[
		{"name": "doctype", "label": "Document Type", "type": "Data"},
		{"name": "name", "label": "Document Name", "type": "Data"},
		{"name": "values", "label": "Field Values (JSON object)", "type": "JSON"},
	],
	allowed_operations=["write"],
)
class FrappeUpdateDocumentNode:
	@staticmethod
	def execute(context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
		doc = frappe.get_doc(config["doctype"], config["name"])
		doc.update(config.get("values") or {})
		doc.save()
		new_context = dict(context)
		new_context["last_document"] = {"doctype": doc.doctype, "name": doc.name}
		return {"context": new_context, "port": "out"}


@node(
	"frappe_submit_document",
	label="Submit Document",
	description="Submits an existing Frappe document via the standard, permission-checked Document API.",
	category="Frappe",
	inputs=[{"name": "in", "multiple": False}],
	outputs=[{"name": "out"}],
	config_schema=[
		{"name": "doctype", "label": "Document Type", "type": "Data"},
		{"name": "name", "label": "Document Name", "type": "Data"},
	],
	allowed_operations=["submit"],
)
class FrappeSubmitDocumentNode:
	@staticmethod
	def execute(context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
		doc = frappe.get_doc(config["doctype"], config["name"])
		doc.submit()
		new_context = dict(context)
		new_context["last_document"] = {"doctype": doc.doctype, "name": doc.name}
		return {"context": new_context, "port": "out"}


@node(
	"frappe_get_document",
	label="Get Document",
	description=(
		"Reads a Frappe document's field values, respecting the execution identity's real "
		"Frappe permissions -- returns no data (not partial/unchecked data) if permission is denied."
	),
	category="Frappe",
	inputs=[{"name": "in", "multiple": False}],
	outputs=[{"name": "out"}],
	config_schema=[
		{"name": "doctype", "label": "Document Type", "type": "Data"},
		{"name": "name", "label": "Document Name", "type": "Data"},
	],
	allowed_operations=["read"],
)
class FrappeGetDocumentNode:
	@staticmethod
	def execute(context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
		doctype = config["doctype"]
		name = config["name"]
		if not frappe.has_permission(doctype, "read", doc=name):
			frappe.throw(
				frappe._("Execution identity {0} does not have read permission on {1} {2}").format(
					frappe.session.user, doctype, name
				),
				frappe.PermissionError,
			)
		doc = frappe.get_doc(doctype, name)
		# Mirrors frappe.client.get's own real (whitelisted, core) document-
		# read path exactly: document-level permission alone is not enough
		# -- a bare doc.as_dict() would leak permlevel-restricted fields
		# (e.g. a User's security-sensitive fields) that this execution
		# identity's real role doesn't have read rights to at the field
		# level, even though it can read the document as a whole.
		doc.apply_fieldlevel_read_permissions()
		new_context = dict(context)
		new_context["document"] = doc.as_dict()
		return {"context": new_context, "port": "out"}


@node(
	"frappe_assignment",
	label="Assignment",
	description="Assigns a document to a user via Frappe's native ToDo-based assignment (frappe.desk.form.assign_to).",
	category="Frappe",
	inputs=[{"name": "in", "multiple": False}],
	outputs=[{"name": "out"}],
	config_schema=[
		{"name": "doctype", "label": "Document Type", "type": "Data"},
		{"name": "name", "label": "Document Name", "type": "Data"},
		{"name": "assign_to", "label": "Assign To (User)", "type": "Data"},
		{"name": "description", "label": "Description", "type": "Small Text"},
	],
	allowed_operations=["write"],
)
class FrappeAssignmentNode:
	@staticmethod
	def execute(context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
		assign_to_add(
			{
				"doctype": config["doctype"],
				"name": config["name"],
				"assign_to": [config["assign_to"]],
				"description": config.get("description"),
			}
		)
		return {"context": context, "port": "out"}


@node(
	"frappe_notification",
	label="Notification",
	description="Sends a native Frappe Notification Log entry (frappe.desk.doctype.notification_log), no raw SMTP.",
	category="Frappe",
	inputs=[{"name": "in", "multiple": False}],
	outputs=[{"name": "out"}],
	config_schema=[
		{"name": "for_user", "label": "Recipient User", "type": "Data"},
		{"name": "subject", "label": "Subject", "type": "Data"},
		{"name": "document_type", "label": "Reference Document Type", "type": "Data"},
		{"name": "document_name", "label": "Reference Document Name", "type": "Data"},
	],
)
class FrappeNotificationNode:
	@staticmethod
	def execute(context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
		enqueue_create_notification(
			users=[config["for_user"]],
			doc={
				"type": "Alert",
				"subject": config.get("subject") or "",
				"document_type": config.get("document_type"),
				"document_name": config.get("document_name"),
				"from_user": frappe.session.user,
			},
		)
		return {"context": context, "port": "out"}


@node(
	"frappe_workflow_action",
	label="Workflow Action",
	description=(
		"Applies a Frappe Workflow transition via frappe.model.workflow.apply_workflow -- "
		"transition validity, role permission, and document state are all validated by that "
		"function itself; this node never reimplements the Workflow engine."
	),
	category="Frappe",
	inputs=[{"name": "in", "multiple": False}],
	outputs=[{"name": "out"}],
	config_schema=[
		{"name": "doctype", "label": "Document Type", "type": "Data"},
		{"name": "name", "label": "Document Name", "type": "Data"},
		{"name": "action", "label": "Workflow Action", "type": "Data"},
	],
	allowed_operations=["write"],
)
class FrappeWorkflowActionNode:
	@staticmethod
	def execute(context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
		apply_workflow({"doctype": config["doctype"], "name": config["name"]}, config["action"])
		return {"context": context, "port": "out"}
