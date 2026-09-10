"""Tests for the Flow Definition DocType and its Flow Version snapshotting
(issue #59). Covers acceptance criteria 1-8 (see also
flow_version/test_flow_version.py for criterion 9, immutability).
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

# Flow Definition/Flow Version don't need generated "User" test records --
# these tests run as the already-authenticated test session user
# (frappe.session.user). Walking User's own link-field dependency chain
# pulls in ERPNext's test-record bootstrap (Company/Price List etc. via
# erpnext.tests.utils's module-level BootStrapTestData() side effect),
# which is unrelated to this DocType and fails on this site's pre-existing
# default data -- excluding it here is the correct, documented mechanism
# (frappe.tests.utils.generators), not a workaround for our own code.
IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]

SIMPLE_NODES = [{"id": "n1", "type": "noop", "position": {"x": 0, "y": 0}, "config": {}}]
SIMPLE_EDGES: list[dict] = []


def _new_flow(flow_name: str, nodes=None, edges=None) -> "frappe.model.document.Document":
	doc = frappe.new_doc("Flow Definition")
	doc.flow_name = flow_name
	doc.schema_version = 1
	doc.nodes = nodes if nodes is not None else SIMPLE_NODES
	doc.edges = edges if edges is not None else SIMPLE_EDGES
	doc.viewport = {"x": 0, "y": 0, "zoom": 1}
	doc.settings = {"on_error": "Stop", "max_steps": 100}
	return doc


class TestFlowDefinition(FrappeTestCase):
	def test_create_flow_definition(self):
		"""1. create Flow Definition"""
		doc = _new_flow("Test Flow Create")
		doc.insert()
		self.assertTrue(frappe.db.exists("Flow Definition", doc.name))

	def test_create_flow_version_snapshot(self):
		"""2. create Flow Version snapshot"""
		doc = _new_flow("Test Flow Snapshot")
		doc.insert()
		versions = frappe.get_all("Flow Version", filters={"flow_definition": doc.name})
		self.assertEqual(len(versions), 1)

	def test_identical_save_does_not_duplicate_snapshot(self):
		"""3. identical save does not duplicate snapshot"""
		doc = _new_flow("Test Flow Dedupe")
		doc.insert()
		first_count = frappe.db.count("Flow Version", {"flow_definition": doc.name})

		# Re-save with byte-for-byte identical graph content.
		doc.reload()
		doc.save()
		second_count = frappe.db.count("Flow Version", {"flow_definition": doc.name})
		self.assertEqual(first_count, second_count)

	def test_changed_graph_creates_new_snapshot(self):
		"""4. changed graph creates new snapshot"""
		doc = _new_flow("Test Flow Change")
		doc.insert()
		first_count = frappe.db.count("Flow Version", {"flow_definition": doc.name})

		doc.nodes = [
			*SIMPLE_NODES,
			{"id": "n2", "type": "noop", "position": {"x": 100, "y": 0}, "config": {}},
		]
		doc.save()
		second_count = frappe.db.count("Flow Version", {"flow_definition": doc.name})
		self.assertEqual(second_count, first_count + 1)

	def test_duplicate_node_id_rejected(self):
		"""5. duplicate node id rejected"""
		doc = _new_flow(
			"Test Flow Duplicate Node",
			nodes=[
				{"id": "n1", "type": "noop", "position": {"x": 0, "y": 0}, "config": {}},
				{"id": "n1", "type": "noop", "position": {"x": 1, "y": 0}, "config": {}},
			],
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert()

	def test_unknown_edge_target_rejected(self):
		"""6. unknown edge target rejected"""
		doc = _new_flow(
			"Test Flow Unknown Edge",
			edges=[{"id": "e1", "source": "n1", "target": "does-not-exist"}],
		)
		with self.assertRaises(frappe.ValidationError):
			doc.insert()

	def test_empty_graph_rejected(self):
		"""7. empty graph rejected"""
		doc = _new_flow("Test Flow Empty", nodes=[])
		with self.assertRaises(frappe.ValidationError):
			doc.insert()

	def test_schema_version_exists_and_persists(self):
		"""8. schema_version exists and persists"""
		doc = _new_flow("Test Flow Schema Version")
		doc.schema_version = 1
		doc.insert()
		doc.reload()
		self.assertEqual(doc.schema_version, 1)
