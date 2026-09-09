"""Tests for execution identity resolution (issue #49)."""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from itsuperapp.agent_flow.identity import resolve_execution_identity

IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]


class TestResolveExecutionIdentity(FrappeTestCase):
	def test_no_default_administrator_identity(self):
		"""1. no default Administrator identity: an all-candidates-empty
		resolution must fail closed, never silently pick Administrator."""
		self.assertIsNone(resolve_execution_identity())

	def test_missing_identity_fails_closed(self):
		"""2. missing identity fails closed: every candidate absent or
		invalid still resolves to None, not an exception, not a default."""
		self.assertIsNone(
			resolve_execution_identity(triggering_user=None, service_user=None, configured_user=None)
		)

	def test_administrator_rejected_from_every_candidate_slot(self):
		"""Administrator must never be resolved, even if explicitly passed
		as the triggering/service/configured candidate -- it is not merely
		a default to avoid, it is disallowed outright (see module docstring)."""
		self.assertIsNone(resolve_execution_identity(triggering_user="Administrator"))
		self.assertIsNone(resolve_execution_identity(service_user="Administrator"))
		self.assertIsNone(resolve_execution_identity(configured_user="Administrator"))

	def test_guest_rejected_from_every_candidate_slot(self):
		self.assertIsNone(resolve_execution_identity(triggering_user="Guest"))
		self.assertIsNone(resolve_execution_identity(service_user="Guest"))
		self.assertIsNone(resolve_execution_identity(configured_user="Guest"))

	def test_disabled_user_is_not_a_valid_identity(self):
		user = frappe.new_doc("User")
		user.email = "wave2-identity-disabled@example.com"
		user.first_name = "Wave2 Disabled"
		user.enabled = 0
		user.send_welcome_email = 0
		user.insert(ignore_permissions=True)
		self.assertIsNone(resolve_execution_identity(triggering_user=user.name))

	def test_triggering_user_resolves_correctly(self):
		"""3. configured service user resolves correctly (and, symmetrically,
		so does a real triggering user) -- the first valid candidate wins."""
		user = frappe.new_doc("User")
		user.email = "wave2-identity-triggering@example.com"
		user.first_name = "Wave2 Triggering"
		user.enabled = 1
		user.send_welcome_email = 0
		user.insert(ignore_permissions=True)
		self.assertEqual(resolve_execution_identity(triggering_user=user.name), user.name)

	def test_configured_service_user_resolves_correctly(self):
		user = frappe.new_doc("User")
		user.email = "wave2-identity-service@example.com"
		user.first_name = "Wave2 Service"
		user.enabled = 1
		user.send_welcome_email = 0
		user.insert(ignore_permissions=True)
		self.assertEqual(resolve_execution_identity(service_user=user.name), user.name)

	def test_priority_order_triggering_before_service_before_configured(self):
		triggering = frappe.new_doc("User")
		triggering.email = "wave2-identity-priority-trig@example.com"
		triggering.first_name = "Wave2 Priority Trig"
		triggering.enabled = 1
		triggering.send_welcome_email = 0
		triggering.insert(ignore_permissions=True)

		service = frappe.new_doc("User")
		service.email = "wave2-identity-priority-svc@example.com"
		service.first_name = "Wave2 Priority Svc"
		service.enabled = 1
		service.send_welcome_email = 0
		service.insert(ignore_permissions=True)

		resolved = resolve_execution_identity(
			triggering_user=triggering.name,
			service_user=service.name,
			configured_user="nonexistent-user@example.com",
		)
		self.assertEqual(resolved, triggering.name)

	def test_invalid_triggering_user_falls_through_to_service_user(self):
		"""An invalid higher-priority candidate (Administrator, disabled,
		or nonexistent) must fall through to the next candidate, not abort
		resolution entirely."""
		service = frappe.new_doc("User")
		service.email = "wave2-identity-fallthrough@example.com"
		service.first_name = "Wave2 Fallthrough"
		service.enabled = 1
		service.send_welcome_email = 0
		service.insert(ignore_permissions=True)

		resolved = resolve_execution_identity(triggering_user="Administrator", service_user=service.name)
		self.assertEqual(resolved, service.name)

	def test_nonexistent_user_is_not_a_valid_identity(self):
		self.assertIsNone(resolve_execution_identity(triggering_user="does-not-exist@example.com"))
