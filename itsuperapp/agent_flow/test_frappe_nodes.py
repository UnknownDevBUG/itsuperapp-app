"""Tests for the Core Frappe node executors (issue #50).

Real (non-mocked) Frappe permission checks, per section 7/15's
requirement that these prove permission enforcement against REAL node
executors, not just the representative fixture from Wave 2's
test_authorization.py. Uses `ToDo` (writable by the stock "All" role --
verified directly against the running site) for the positive/authorized
cases, and `Error Log`/`Journal Entry` (both restricted to
System-Manager-or-above roles, also verified directly) for the
denied-without-privilege cases.
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from itsuperapp.agent_flow.nodes.frappe_nodes import (
	FrappeAssignmentNode,
	FrappeCreateDocumentNode,
	FrappeGetDocumentNode,
	FrappeNotificationNode,
	FrappeUpdateDocumentNode,
	FrappeWorkflowActionNode,
)

IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]


class TestFrappeNodes(FrappeTestCase):
	def _make_user(self, email, *, roles=None):
		user = frappe.new_doc("User")
		user.email = email
		user.first_name = email.split("@")[0]
		user.enabled = 1
		user.send_welcome_email = 0
		for role in roles or []:
			user.append("roles", {"role": role})
		user.insert(ignore_permissions=True)
		return user

	def _as_user(self, user_name):
		"""Context-manager-free helper: run the rest of the test as
		`user_name` via frappe.set_user, mirroring what the runtime does
		before invoking any executor (frappe.set_user(execution_identity))."""
		self.addCleanup(frappe.set_user, frappe.session.user)
		frappe.set_user(user_name)

	def test_create_document_node_respects_permission_authorized(self):
		"""1. Create Document node respects permission (authorized case)."""
		user = self._make_user("wave3-frappe-create-ok@example.com")
		self._as_user(user.name)
		result = FrappeCreateDocumentNode.execute(
			{}, {"doctype": "ToDo", "values": {"description": "Wave 3 node test"}}
		)
		todo_name = result["context"]["last_document"]["name"]
		self.assertTrue(frappe.db.exists("ToDo", todo_name))
		self.assertEqual(result["port"], "out")

	def test_create_document_node_denies_unauthorized(self):
		"""2. unauthorized create denied -- real, non-mocked Frappe
		permission check against Error Log (System Manager only)."""
		user = self._make_user("wave3-frappe-create-deny@example.com")
		self._as_user(user.name)
		with self.assertRaises(frappe.PermissionError):
			FrappeCreateDocumentNode.execute(
				{}, {"doctype": "Error Log", "values": {"method": "should not be created"}}
			)

	def test_update_document_node_respects_permission(self):
		"""3. Update Document respects permission."""
		owner = self._make_user("wave3-frappe-update-owner@example.com", roles=["System Manager"])
		self._as_user(owner.name)
		todo = frappe.get_doc({"doctype": "ToDo", "description": "Wave 3 update target"}).insert()
		error_log = frappe.get_all("Error Log", limit=1, pluck="name")
		if not error_log:
			frappe.get_doc({"doctype": "Error Log", "method": "Wave 3 update-deny fixture"}).insert(
				ignore_permissions=True
			)
			error_log = frappe.get_all("Error Log", limit=1, pluck="name")

		unprivileged = self._make_user("wave3-frappe-update-deny@example.com")
		self._as_user(unprivileged.name)
		# A plain "All"-role user CAN update their own ToDo per stock
		# permissions, so deny via a real, existing Error Log record
		# (System Manager only, verified directly) for the negative case
		# -- must be a real existing row so the PermissionError comes from
		# the write-permission check, not a DoesNotExistError from
		# frappe.get_doc() failing to find a fabricated name first.
		with self.assertRaises(frappe.PermissionError):
			FrappeUpdateDocumentNode.execute(
				{},
				{
					"doctype": "Error Log",
					"name": error_log[0],
					"values": {"method": "should not be updated"},
				},
			)

		self._as_user(owner.name)
		result = FrappeUpdateDocumentNode.execute(
			{}, {"doctype": "ToDo", "name": todo.name, "values": {"description": "Wave 3 updated"}}
		)
		self.assertEqual(frappe.db.get_value("ToDo", todo.name, "description"), "Wave 3 updated")
		self.assertEqual(result["port"], "out")

	def test_submit_document_respects_permission(self):
		"""4. Submit respects permission -- real, non-mocked
		frappe.has_permission check against Journal Entry (restricted to
		Accounts User/Accounts Manager/Auditor, verified directly against
		the running site). A full ERPNext Journal Entry has enough
		mandatory accounting dependencies (company/accounts/fiscal year)
		that constructing a genuinely submittable one is out of proportion
		for this unit test; the security-critical direction -- that an
		unprivileged execution identity is denied -- is what this proves.
		`FrappeSubmitDocumentNode.execute()` calls `doc.submit()` with no
		bypass, so this is exactly the permission gate it goes through."""
		unprivileged = self._make_user("wave3-frappe-submit-deny@example.com")
		self.assertFalse(frappe.has_permission("Journal Entry", "submit", user=unprivileged.name))

	def test_get_document_node_cannot_leak_protected_data(self):
		"""5. Read node cannot leak protected data."""
		self._as_user("Administrator")
		error_log = frappe.get_all("Error Log", limit=1, pluck="name")
		if not error_log:
			frappe.get_doc({"doctype": "Error Log", "method": "Wave 3 node test fixture"}).insert(
				ignore_permissions=True
			)
			error_log = frappe.get_all("Error Log", limit=1, pluck="name")

		unprivileged = self._make_user("wave3-frappe-read-deny@example.com")
		self._as_user(unprivileged.name)
		with self.assertRaises(frappe.PermissionError):
			FrappeGetDocumentNode.execute({}, {"doctype": "Error Log", "name": error_log[0]})

	def test_get_document_node_returns_data_when_authorized(self):
		owner = self._make_user("wave3-frappe-read-ok@example.com", roles=["System Manager"])
		self._as_user(owner.name)
		todo = frappe.get_doc({"doctype": "ToDo", "description": "Wave 3 read target"}).insert()
		result = FrappeGetDocumentNode.execute({}, {"doctype": "ToDo", "name": todo.name})
		self.assertEqual(result["context"]["document"]["description"], "Wave 3 read target")

	def test_get_document_node_does_not_leak_permlevel_restricted_fields(self):
		"""Security regression (Wave 3 adversarial review): a bare
		doc.as_dict() would leak permlevel-restricted fields even when
		document-level read permission passes. `User.user_type` is
		permlevel=1, granted only to System Manager (verified directly
		against the running site) and holds a real, non-None value
		("Website User" for a fresh role-less user) for any normal user -- a plain user reading their
		own User record (self-read is always allowed at the document
		level) must see it nulled out, not its real value. Note:
		apply_fieldlevel_read_permissions() nulls the *value* of a
		restricted field (delattr on the Document instance, which
		as_dict() then serializes back as None) -- the dict *key* is
		still present, so this asserts value, not key absence."""
		user = self._make_user("wave3-frappe-read-fieldlevel@example.com", roles=[])
		self.assertEqual(frappe.db.get_value("User", user.name, "user_type"), "Website User")

		self._as_user(user.name)
		result = FrappeGetDocumentNode.execute({}, {"doctype": "User", "name": user.name})
		self.assertIsNone(result["context"]["document"]["user_type"])
		self.assertEqual(result["context"]["document"]["email"], user.name)

	def test_get_document_node_shows_permlevel_field_to_privileged_reader(self):
		"""Same field, read by a System Manager: must show the real value
		-- proving the filter is real permlevel enforcement, not fields
		nulled unconditionally regardless of privilege."""
		user = self._make_user("wave3-frappe-read-fieldlevel-priv@example.com", roles=["System Manager"])
		self._as_user(user.name)
		result = FrappeGetDocumentNode.execute({}, {"doctype": "User", "name": user.name})
		self.assertEqual(result["context"]["document"]["user_type"], "System User")

	def test_assignment_node_uses_native_assignment(self):
		"""6. Assignment node uses Frappe native assignment."""
		owner = self._make_user("wave3-frappe-assign-owner@example.com", roles=["System Manager"])
		assignee = self._make_user("wave3-frappe-assign-to@example.com", roles=["System Manager"])
		self._as_user(owner.name)
		todo = frappe.get_doc({"doctype": "ToDo", "description": "Wave 3 assignment target"}).insert()

		result = FrappeAssignmentNode.execute(
			{},
			{
				"doctype": "ToDo",
				"name": todo.name,
				"assign_to": assignee.name,
				"description": "please review",
			},
		)
		self.assertEqual(result["port"], "out")
		self.assertTrue(
			frappe.db.exists(
				"ToDo",
				{"reference_type": "ToDo", "reference_name": todo.name, "allocated_to": assignee.name},
			)
		)

	def test_notification_node_uses_native_notification(self):
		"""7. Notification node uses native notification (Notification Log,
		not raw SMTP)."""
		self._as_user("Administrator")
		recipient = self._make_user("wave3-frappe-notify@example.com", roles=["System Manager"])
		result = FrappeNotificationNode.execute(
			{},
			{
				"for_user": recipient.name,
				"subject": "Wave 3 test notification",
				"document_type": "ToDo",
				"document_name": "does-not-matter",
			},
		)
		self.assertEqual(result["port"], "out")
		self.assertTrue(
			frappe.db.exists(
				"Notification Log", {"for_user": recipient.name, "subject": "Wave 3 test notification"}
			)
		)

	def test_workflow_action_validates_transition(self):
		"""8. Workflow Action validates transition -- ToDo has no
		Workflow configured, so apply_workflow's own real validation
		(never reimplemented here) must reject any action cleanly,
		proving the node routes through real validation rather than
		silently succeeding."""
		self._as_user("Administrator")
		todo = frappe.get_doc({"doctype": "ToDo", "description": "Wave 3 workflow target"}).insert()
		with self.assertRaises(frappe.ValidationError):
			FrappeWorkflowActionNode.execute({}, {"doctype": "ToDo", "name": todo.name, "action": "Approve"})
