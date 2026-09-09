"""Tests for the Flow Version DocType (issue #59)."""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

# See test_flow_definition.py for why "User" is excluded here.
IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]


class TestFlowVersion(FrappeTestCase):
	def test_immutable_flow_version_cannot_be_silently_mutated(self):
		"""9. immutable Flow Version cannot be silently mutated"""
		flow = frappe.new_doc("Flow Definition")
		flow.flow_name = "Test Flow For Immutability"
		flow.schema_version = 1
		flow.nodes = [{"id": "n1", "type": "noop", "position": {"x": 0, "y": 0}, "config": {}}]
		flow.edges = []
		flow.viewport = {"x": 0, "y": 0, "zoom": 1}
		flow.settings = {}
		flow.insert()

		version_name = frappe.get_all("Flow Version", filters={"flow_definition": flow.name}, pluck="name")[0]
		version = frappe.get_doc("Flow Version", version_name)
		version.label = "attempted mutation"
		with self.assertRaises(frappe.ValidationError):
			version.save()
