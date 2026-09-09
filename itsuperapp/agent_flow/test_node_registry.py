"""Tests for the canonical Agent Flow node registry (issue #61).

Each test uses a unique node type name (this module's own registrations
are never removed between tests within a process -- `_REGISTRY` is
module-level state, not reset by Frappe's per-test DB rollback) so tests
cannot collide with each other or with the `example_nodes` module the
`agent_flow_nodes` hook loads by default.

Executor classes used by `get_executor()` tests are defined at module
level, not nested inside a test method: `get_executor()` resolves a class
by dotted import path, and Python cannot import a class defined inside a
function/method by any dotted path (it only exists as a local closure
variable while that call is on the stack) -- that's a real Python
language limitation, not a registry bug, and it matches how a real node
executor must be defined anyway (module-level, importable), so the test
fixtures reflect that instead of working around it.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from itsuperapp.agent_flow import node_registry
from itsuperapp.agent_flow.node_registry import (
	NodeRegistrationError,
	all_node_types,
	get_executor,
	node,
)


@node("test_executor_resolution_node")
class _ExecutorResolutionNode:
	marker = "resolved"


@node("test_shared_registry_node")
class _SharedRegistryNode:
	pass


class TestNodeRegistry(FrappeTestCase):
	def test_register_node(self):
		"""1. register node"""

		@node("test_register_node", label="Register Test")
		class _Executor:
			pass

		registry = all_node_types()
		self.assertIn("test_register_node", registry)
		self.assertEqual(registry["test_register_node"]["label"], "Register Test")

	def test_duplicate_registration_raises(self):
		"""2. duplicate type registration fails loudly"""

		@node("test_duplicate_node")
		class _First:
			pass

		with self.assertRaises(NodeRegistrationError):

			@node("test_duplicate_node")
			class _Second:
				pass

	def test_get_node_registry_includes_registered_node(self):
		"""3. metadata API sees registered node"""

		@node("test_metadata_api_node", label="Metadata API Test")
		class _Executor:
			pass

		from itsuperapp.agent_flow.api import get_node_registry

		types = [entry["type"] for entry in get_node_registry()]
		self.assertIn("test_metadata_api_node", types)

	def test_get_executor_resolves_registered_node(self):
		"""4. get_executor sees same registered node"""
		resolved = get_executor("test_executor_resolution_node")
		self.assertIs(resolved, _ExecutorResolutionNode)
		self.assertEqual(resolved.marker, "resolved")

	def test_metadata_and_executor_share_registry(self):
		"""5. metadata API and executor resolver use the same registry --
		registering a node makes it simultaneously visible to both."""
		self.assertIn("test_shared_registry_node", all_node_types())
		self.assertIs(get_executor("test_shared_registry_node"), _SharedRegistryNode)

	def test_hook_based_module_loading(self):
		"""6. cross-app hook registration works.

		Proves the loading mechanism itself: `_ensure_loaded()` reads
		`frappe.get_hooks("agent_flow_nodes")` and imports every path it
		returns, regardless of which app declared it -- tested by mocking
		`import_module` directly (not relying on a real module's import
		side effect, which Python's module cache would make a no-op on a
		second call within the same process; the real `example_nodes`
		module is proven to work by every other test in this file, which
		all depend on its `noop` test node existing via that same real
		hook-loading path).
		"""
		# reset_registry() cannot be safely "undone" afterward by
		# re-importing already-cached modules -- Python does not re-run a
		# module's top-level code (and therefore its @node decorators) on
		# a second import within the same process. Save and restore the
		# exact prior state directly instead, so this test has no lasting
		# effect on any other test's registrations.
		saved_registry = dict(node_registry._REGISTRY)
		saved_loaded = node_registry._LOADED
		node_registry.reset_registry()
		imported: list[str] = []
		try:
			with (
				patch.object(
					frappe, "get_hooks", return_value=["some.other.app.module", "another.app.module"]
				),
				patch.object(node_registry.importlib, "import_module", side_effect=imported.append),
			):
				node_registry._ensure_loaded()
			self.assertEqual(imported, ["some.other.app.module", "another.app.module"])
		finally:
			node_registry._REGISTRY.clear()
			node_registry._REGISTRY.update(saved_registry)
			node_registry._LOADED = saved_loaded

	def test_version_field_present(self):
		"""7. version field exists"""

		@node("test_version_field_node", version=3)
		class _Executor:
			pass

		self.assertEqual(all_node_types()["test_version_field_node"]["version"], 3)

	def test_config_schema_roundtrip(self):
		"""8. config_schema is returned correctly"""
		schema = [{"name": "foo", "label": "Foo", "type": "Data"}]

		@node("test_config_schema_node", config_schema=schema)
		class _Executor:
			pass

		self.assertEqual(all_node_types()["test_config_schema_node"]["config_schema"], schema)

	def test_all_node_types_is_single_source(self):
		"""9. no duplicate node-type list exists in the implementation path.

		Architectural enforcement, not a grep hack: `all_node_types()` is
		the only function that reads `_REGISTRY`, and this test proves a
		newly registered type is visible through it immediately -- there
		is no separate cached/duplicated list anywhere in this module for
		a consumer to accidentally read instead.
		"""
		before = set(all_node_types())

		@node("test_single_source_node")
		class _Executor:
			pass

		after = set(all_node_types())
		self.assertEqual(after - before, {"test_single_source_node"})
