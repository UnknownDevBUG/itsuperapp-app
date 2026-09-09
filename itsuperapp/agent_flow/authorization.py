"""Centralized node-operation permission gateway (issue #49).

ADR 0012 Security Model: every Frappe operation a node performs must be
checked against all four layers below, through this one wrapper -- never
an optional convention each executor remembers on its own (the exact gap
Official Flow has and FlowAgent utterly lacks, per ADR 0013's evaluation).
No runtime code may call `frappe.get_doc`/`frappe.get_all`/`insert`/
`save`/`submit` on a node's behalf without first passing
`authorize_node_operation()` for that operation.

Layers, all of which must pass:

    1. Frappe permission   -- `frappe.has_permission(doctype, ptype, doc,
                               user=execution_identity)`, explicit
                               `user=`, never implicit `frappe.session.user`.
    2. Flow permission      -- can this identity use this Flow Definition
                               at all (independent of DocType permissions).
    3. Node permission      -- can this identity use this specific node
                               *type* (a node's `permissions` list in the
                               canonical registry, e.g. elevated-role-only
                               node types).
    4. Allowed operation    -- the specific operation requested is one the
                               node type actually declares/supports, not
                               merely "some permission exists somewhere".

Denial raises `frappe.PermissionError`/`frappe.ValidationError` (never
returns a boolean the caller might forget to check) -- the runtime must
let this propagate to its own step-failure handling, never swallow it.
"""

from __future__ import annotations

import frappe

from itsuperapp.agent_flow.node_registry import all_node_types

_OPERATION_TO_PTYPE = {
	"read": "read",
	"write": "write",
	"create": "create",
	"submit": "submit",
	"cancel": "cancel",
	"delete": "delete",
}


def authorize_node_operation(
	*,
	execution_identity: str,
	flow_definition: str,
	node_type: str,
	operation: str = "read",
	doctype: str | None = None,
	doc: str | dict | None = None,
) -> None:
	"""Authorize one node's attempt to perform `operation`, raising on denial.

	Always checks Flow permission, Node permission, and Allowed operation.
	Additionally checks Frappe permission when `doctype` is given (a node
	that performs no Frappe document operation -- e.g. a pure data/logic
	node -- has nothing to check at that layer).
	"""
	entry = _require_registered_node(node_type)
	_check_flow_permission(execution_identity, flow_definition)
	_check_node_permission(execution_identity, entry)
	_check_allowed_operation(entry, operation)
	if doctype:
		_check_frappe_permission(execution_identity, doctype, operation, doc)


def _require_registered_node(node_type: str) -> dict:
	entry = all_node_types().get(node_type)
	if entry is None:
		frappe.throw(
			frappe._("Unknown Agent Flow node type: {0}").format(node_type),
			frappe.ValidationError,
		)
	return entry


def _check_frappe_permission(user: str, doctype: str, operation: str, doc) -> None:
	ptype = _OPERATION_TO_PTYPE.get(operation, "read")
	if not frappe.has_permission(doctype, ptype, doc=doc, user=user):
		frappe.throw(
			frappe._("User {0} does not have {1} permission on {2}").format(user, ptype, doctype),
			frappe.PermissionError,
		)


def _check_flow_permission(user: str, flow_definition: str) -> None:
	if not frappe.has_permission("Flow Definition", "read", doc=flow_definition, user=user):
		frappe.throw(
			frappe._("User {0} does not have permission to use Flow Definition {1}").format(
				user, flow_definition
			),
			frappe.PermissionError,
		)


def _check_node_permission(user: str, entry: dict) -> None:
	required_roles = entry.get("permissions") or []
	if not required_roles:
		return
	user_roles = set(frappe.get_roles(user))
	if not user_roles.intersection(required_roles):
		frappe.throw(
			frappe._("User {0} lacks a required role for node type {1}: needs one of {2}").format(
				user, entry["type"], ", ".join(required_roles)
			),
			frappe.PermissionError,
		)


def _check_allowed_operation(entry: dict, operation: str) -> None:
	allowed = entry.get("allowed_operations") or []
	# A node with no declared `allowed_operations` has nothing further to
	# narrow at this layer once Flow/Node/Frappe permission already
	# passed -- most node types (e.g. this package's noop/set_variable
	# examples) never touch a Frappe document and don't declare any.
	if not allowed:
		return
	if operation not in allowed:
		frappe.throw(
			frappe._("Operation {0} is not permitted for this node type (allowed: {1})").format(
				operation, ", ".join(sorted(allowed))
			),
			frappe.PermissionError,
		)
