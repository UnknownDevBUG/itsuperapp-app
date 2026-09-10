"""Tests for the Agent Flow Trigger DocType (issue #62) -- data model
validation: 1-6 in the required test list."""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]


class TestAgentFlowTrigger(FrappeTestCase):
	def _make_user(self, email, *, roles=("System Manager",), enabled=1):
		user = frappe.new_doc("User")
		user.email = email
		user.first_name = email.split("@")[0]
		user.enabled = enabled
		user.send_welcome_email = 0
		for role in roles:
			user.append("roles", {"role": role})
		user.insert(ignore_permissions=True)
		return user

	def _make_flow(self):
		flow = frappe.new_doc("Flow Definition")
		flow.flow_name = f"Wave4 Trigger Test Flow {frappe.generate_hash(length=8)}"
		flow.schema_version = 1
		flow.nodes = [{"id": "n1", "type": "noop", "position": {}, "config": {}}]
		flow.edges = []
		flow.viewport = {"x": 0, "y": 0, "zoom": 1}
		flow.settings = {}
		flow.insert(ignore_permissions=True)
		return flow

	def test_create_enabled_trigger(self):
		"""1. create enabled trigger."""
		flow = self._make_flow()
		user = self._make_user("wave4-trigger-create@example.com")
		trigger = frappe.get_doc(
			{
				"doctype": "Agent Flow Trigger",
				"flow_definition": flow.name,
				"enabled": 1,
				"trigger_type": "DocType Event",
				"service_user": user.name,
				"event_doctype": "ToDo",
				"event_name": "after_insert",
			}
		).insert(ignore_permissions=True)
		self.assertEqual(trigger.enabled, 1)

	def test_invalid_trigger_config_rejected(self):
		"""2. invalid trigger config rejected -- bad cron format."""
		flow = self._make_flow()
		user = self._make_user("wave4-trigger-invalid@example.com")
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Agent Flow Trigger",
					"flow_definition": flow.name,
					"trigger_type": "Schedule",
					"service_user": user.name,
					"cron_format": "not a cron expression",
				}
			).insert(ignore_permissions=True)

	def test_disabled_trigger_does_not_run(self):
		"""3. disabled trigger does not run -- proven at the dispatch layer
		in test_triggers_doctype_event.py; here, confirm a disabled
		trigger is correctly excluded from the enabled-only lookup."""
		flow = self._make_flow()
		user = self._make_user("wave4-trigger-disabled@example.com")
		trigger = frappe.get_doc(
			{
				"doctype": "Agent Flow Trigger",
				"flow_definition": flow.name,
				"enabled": 0,
				"trigger_type": "DocType Event",
				"service_user": user.name,
				"event_doctype": "ToDo",
				"event_name": "after_insert",
			}
		).insert(ignore_permissions=True)
		matches = frappe.get_all(
			"Agent Flow Trigger",
			filters={
				"enabled": 1,
				"trigger_type": "DocType Event",
				"event_doctype": "ToDo",
				"event_name": "after_insert",
				"name": trigger.name,
			},
		)
		self.assertEqual(matches, [])

	def test_invalid_service_user_rejected(self):
		"""4. invalid service user rejected."""
		flow = self._make_flow()
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Agent Flow Trigger",
					"flow_definition": flow.name,
					"trigger_type": "DocType Event",
					"service_user": "does-not-exist@example.com",
					"event_doctype": "ToDo",
					"event_name": "after_insert",
				}
			).insert(ignore_permissions=True)

	def test_administrator_rejected_as_service_user(self):
		"""5. Administrator rejected."""
		flow = self._make_flow()
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Agent Flow Trigger",
					"flow_definition": flow.name,
					"trigger_type": "DocType Event",
					"service_user": "Administrator",
					"event_doctype": "ToDo",
					"event_name": "after_insert",
				}
			).insert(ignore_permissions=True)

	def test_guest_rejected_as_service_user(self):
		"""6. Guest rejected."""
		flow = self._make_flow()
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Agent Flow Trigger",
					"flow_definition": flow.name,
					"trigger_type": "DocType Event",
					"service_user": "Guest",
					"event_doctype": "ToDo",
					"event_name": "after_insert",
				}
			).insert(ignore_permissions=True)

	def test_webhook_trigger_generates_key_and_rejects_missing_secret(self):
		flow = self._make_flow()
		user = self._make_user("wave4-trigger-webhook@example.com")
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Agent Flow Trigger",
					"flow_definition": flow.name,
					"trigger_type": "Webhook",
					"service_user": user.name,
				}
			).insert(ignore_permissions=True)

		trigger = frappe.get_doc(
			{
				"doctype": "Agent Flow Trigger",
				"flow_definition": flow.name,
				"trigger_type": "Webhook",
				"service_user": user.name,
				"webhook_secret": "a-real-secret-value",
			}
		).insert(ignore_permissions=True)
		self.assertTrue(trigger.webhook_key)

	def test_disabled_service_user_rejected(self):
		flow = self._make_flow()
		user = self._make_user("wave4-trigger-svcdisabled@example.com", enabled=0)
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Agent Flow Trigger",
					"flow_definition": flow.name,
					"trigger_type": "DocType Event",
					"service_user": user.name,
					"event_doctype": "ToDo",
					"event_name": "after_insert",
				}
			).insert(ignore_permissions=True)

	def test_unknown_doctype_event_rejected(self):
		flow = self._make_flow()
		user = self._make_user("wave4-trigger-unknowndt@example.com")
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Agent Flow Trigger",
					"flow_definition": flow.name,
					"trigger_type": "DocType Event",
					"service_user": user.name,
					"event_doctype": "Totally Not A Real DocType",
					"event_name": "after_insert",
				}
			).insert(ignore_permissions=True)
