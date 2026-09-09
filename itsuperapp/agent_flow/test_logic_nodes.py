"""Tests for Logic node executors (issue #50)."""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from itsuperapp.agent_flow.nodes.logic_nodes import LogicConditionNode

IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]


class TestLogicConditionNode(FrappeTestCase):
	def test_condition_selects_out_yes_when_true(self):
		"""9. Condition selects correct output."""
		result = LogicConditionNode.execute({}, {"left": 5, "operator": ">", "right": 3})
		self.assertEqual(result["port"], "out-yes")

	def test_condition_selects_out_no_when_false(self):
		result = LogicConditionNode.execute({}, {"left": 2, "operator": ">", "right": 3})
		self.assertEqual(result["port"], "out-no")

	def test_condition_renders_context_placeholders(self):
		result = LogicConditionNode.execute({"x": 10}, {"left": "{{ x }}", "operator": "==", "right": "10"})
		self.assertEqual(result["port"], "out-yes")

	def test_condition_unknown_operator_fails_predictably(self):
		with self.assertRaises(frappe.ValidationError):
			LogicConditionNode.execute({}, {"left": 1, "operator": "__import__", "right": 1})
