"""Tests for the Human Approval node and its secure token-based resume
(issue #50) -- end-to-end through the real runtime (issue #48), not the
node executor in isolation, since the token/notification mechanics live
in runtime.py's NodeWaiting/resume_flow_run_with_token, not the node.
"""

from __future__ import annotations

import re

import frappe
from frappe.tests.utils import FrappeTestCase

from itsuperapp.agent_flow.runtime import (
	create_flow_run,
	execute_flow_run,
	resume_flow_run_with_token,
)

IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]


class TestHumanApproval(FrappeTestCase):
	def _make_user(self, email, *, roles=("System Manager",)):
		user = frappe.new_doc("User")
		user.email = email
		user.first_name = email.split("@")[0]
		user.enabled = 1
		user.send_welcome_email = 0
		for role in roles:
			user.append("roles", {"role": role})
		user.insert(ignore_permissions=True)
		return user

	def _make_flow(self, approver_email):
		flow = frappe.new_doc("Flow Definition")
		flow.flow_name = f"Wave3 Approval Test Flow {frappe.generate_hash(length=8)}"
		flow.schema_version = 1
		flow.nodes = [
			{
				"id": "n1",
				"type": "human_approval",
				"position": {},
				"config": {"approver": approver_email, "subject": "Please approve"},
			},
			{"id": "n2", "type": "noop", "position": {}, "config": {}},
		]
		flow.edges = [{"id": "e1", "source": "n1", "target": "n2"}]
		flow.viewport = {"x": 0, "y": 0, "zoom": 1}
		flow.settings = {}
		flow.insert(ignore_permissions=True)
		return flow

	def _extract_token(self, notification_content: str) -> str:
		match = re.search(r"token=([\w\-]+)", notification_content)
		self.assertIsNotNone(match, "resume link with token not found in notification content")
		return match.group(1)

	def test_human_approval_moves_run_to_waiting(self):
		"""11. Human Approval moves run to WAITING."""
		triggering = self._make_user("wave3-approval-trigger@example.com")
		approver = self._make_user("wave3-approval-approver@example.com")
		flow = self._make_flow(approver.name)
		run_name = create_flow_run(
			flow_definition=flow.name, config={}, source="Manual", triggering_user=triggering.name
		)
		execute_flow_run(run_name)
		run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(run.status, "Waiting")

	def test_authorized_resume_with_token_continues(self):
		"""12. authorized resume continues."""
		triggering = self._make_user("wave3-approval-trigger-ok@example.com")
		approver = self._make_user("wave3-approval-approver-ok@example.com")
		flow = self._make_flow(approver.name)
		run_name = create_flow_run(
			flow_definition=flow.name, config={}, source="Manual", triggering_user=triggering.name
		)
		execute_flow_run(run_name)

		notification = frappe.get_doc(
			"Notification Log", {"for_user": approver.name, "document_name": run_name}
		)
		token = self._extract_token(notification.email_content)

		original_user = frappe.session.user
		frappe.set_user(approver.name)
		try:
			resume_flow_run_with_token(run_name, token)
		finally:
			frappe.set_user(original_user)
		execute_flow_run(run_name)

		run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(run.status, "Success")

	def test_unauthorized_resume_denied(self):
		"""13. unauthorized resume denied -- wrong token is rejected."""
		triggering = self._make_user("wave3-approval-trigger-bad@example.com")
		approver = self._make_user("wave3-approval-approver-bad@example.com")
		flow = self._make_flow(approver.name)
		run_name = create_flow_run(
			flow_definition=flow.name, config={}, source="Manual", triggering_user=triggering.name
		)
		execute_flow_run(run_name)

		attacker = self._make_user("wave3-approval-attacker@example.com", roles=[])
		original_user = frappe.session.user
		frappe.set_user(attacker.name)
		try:
			with self.assertRaises(frappe.PermissionError):
				resume_flow_run_with_token(run_name, "totally-wrong-token")
		finally:
			frappe.set_user(original_user)
		self.assertEqual(frappe.db.get_value("Flow Run", run_name, "status"), "Waiting")

	def test_replay_resume_with_same_token_denied(self):
		"""14. replay resume denied -- a token can be consumed exactly once."""
		triggering = self._make_user("wave3-approval-trigger-replay@example.com")
		approver = self._make_user("wave3-approval-approver-replay@example.com")
		flow = self._make_flow(approver.name)
		run_name = create_flow_run(
			flow_definition=flow.name, config={}, source="Manual", triggering_user=triggering.name
		)
		execute_flow_run(run_name)

		notification = frappe.get_doc(
			"Notification Log", {"for_user": approver.name, "document_name": run_name}
		)
		token = self._extract_token(notification.email_content)

		original_user = frappe.session.user
		frappe.set_user(approver.name)
		try:
			resume_flow_run_with_token(run_name, token)
			with self.assertRaises(frappe.PermissionError):
				resume_flow_run_with_token(run_name, token)
		finally:
			frappe.set_user(original_user)

	def test_unauthenticated_guest_resume_rejected(self):
		"""Human Approval security requirement: never a public
		unauthenticated unrestricted resume."""
		triggering = self._make_user("wave3-approval-trigger-guest@example.com")
		approver = self._make_user("wave3-approval-approver-guest@example.com")
		flow = self._make_flow(approver.name)
		run_name = create_flow_run(
			flow_definition=flow.name, config={}, source="Manual", triggering_user=triggering.name
		)
		execute_flow_run(run_name)
		notification = frappe.get_doc(
			"Notification Log", {"for_user": approver.name, "document_name": run_name}
		)
		token = self._extract_token(notification.email_content)

		original_user = frappe.session.user
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				resume_flow_run_with_token(run_name, token)
		finally:
			frappe.set_user(original_user)
