"""Canonical Agent Flow node registry (issue #61).

Single source of truth: a Python decorator registry, per
docs/architecture/agent-flow-design.md -> "Canonical Node Registry".
Every consumer (execution engine, Studio palette, a future AI-Build
feature) must read node-type metadata through `all_node_types()` /
`get_node_registry()` / `get_executor()` -- never maintain its own
hand-copied node-type list. This is the direct, named fix for a
confirmed FlowAgent production bug (STEP 2 finding): its AI-Build
whitelist silently dropped node types because it was a manually
maintained third copy that drifted from the real registry.

Cross-app registration: any installed app (including this one) lists the
dotted path of a module containing `@node(...)`-decorated classes under
the `agent_flow_nodes` hook in its own hooks.py. Nothing needs to edit a
central file to add a node type.
"""

from __future__ import annotations

import importlib
from typing import Any

import frappe

_REGISTRY: dict[str, dict[str, Any]] = {}
_LOADED = False


class NodeRegistrationError(Exception):
	"""Raised when a node type is registered more than once."""


def node(
	type_name: str,
	*,
	version: int = 1,
	label: str | None = None,
	description: str = "",
	category: str = "Data",
	icon: str = "gear",
	inputs: list[dict[str, Any]] | None = None,
	outputs: list[dict[str, Any]] | None = None,
	config_schema: list[dict[str, Any]] | None = None,
	permissions: list[str] | None = None,
	capabilities: list[str] | None = None,
	allowed_operations: list[str] | None = None,
):
	"""Register an executor class under a canonical node `type_name`.

	Fields mirror docs/architecture/agent-flow-design.md's node definition
	table exactly. `version` is bumped on a breaking `config_schema`
	change -- this field is the direct fix for the node-type drift bug
	found in FlowAgent's `VALID_NODE_TYPES` (STEP 2 finding).

	`allowed_operations` is the fourth permission-gate layer from ADR 0012's
	Security Model ("Allowed operation" -- issue #49): the specific
	operations (e.g. "read", "write", "submit") this node type may request
	through `authorization.authorize_node_operation()`. `None`/empty means
	no restriction beyond the other three layers -- most nodes (including
	both example nodes in this package) don't touch a Frappe document at
	all, so they have nothing to restrict here.

	Raises NodeRegistrationError if `type_name` is already registered --
	registration failure is loud, never silent (acceptance criterion).
	"""

	def _decorator(executor_cls):
		if type_name in _REGISTRY:
			existing_executor = _REGISTRY[type_name]["executor"]
			raise NodeRegistrationError(
				f"Node type '{type_name}' is already registered by "
				f"'{existing_executor}'; cannot register "
				f"'{executor_cls.__module__}.{executor_cls.__qualname__}'. "
				"Choose a different type_name or remove the existing "
				"registration."
			)
		_REGISTRY[type_name] = {
			"type": type_name,
			"version": version,
			"label": label or type_name,
			"description": description,
			"category": category,
			"icon": icon,
			"inputs": inputs or [],
			"outputs": outputs or [],
			"config_schema": config_schema or [],
			"permissions": permissions or [],
			"executor": f"{executor_cls.__module__}.{executor_cls.__qualname__}",
			"capabilities": capabilities or [],
			"allowed_operations": allowed_operations or [],
		}
		executor_cls.node_type = type_name
		return executor_cls

	return _decorator


def _ensure_loaded() -> None:
	"""Import every module listed under the `agent_flow_nodes` hook.

	Importing a module containing `@node(...)`-decorated classes triggers
	those decorators, populating `_REGISTRY`. Runs once per process; call
	`reset_registry()` (tests only) to force a reload.
	"""
	global _LOADED
	if _LOADED:
		return
	_LOADED = True
	for module_path in frappe.get_hooks("agent_flow_nodes") or []:
		importlib.import_module(module_path)


def reset_registry() -> None:
	"""Clear all registered nodes and the loaded flag.

	Test-only: production code never needs to unregister a node type.
	"""
	_REGISTRY.clear()
	global _LOADED
	_LOADED = False


def all_node_types() -> dict[str, dict[str, Any]]:
	"""Return the full registry, keyed by node type.

	This is the single source of truth every consumer must read from --
	never copy this into a separate list.
	"""
	_ensure_loaded()
	return dict(_REGISTRY)


def get_executor(type_name: str):
	"""Resolve and return the executor class registered for `type_name`.

	Reads the same underlying dict `all_node_types()` reads -- metadata
	and execution can never see a different registered node.
	"""
	_ensure_loaded()
	entry = _REGISTRY.get(type_name)
	if not entry:
		frappe.throw(frappe._("Unknown Agent Flow node type: {0}").format(type_name))
	module_path, class_name = entry["executor"].rsplit(".", 1)
	module = importlib.import_module(module_path)
	return getattr(module, class_name)
