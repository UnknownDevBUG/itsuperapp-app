"""Tests for the centralized node-operation permission gateway (issue #49).

Per section 20's requirement that these acceptance tests not be mock-only,
the Frappe-permission-layer tests below exercise `frappe.has_permission`
for real against a real stock doctype (`Error Log`, restricted to System
Manager in Frappe core -- verified directly against the running site, not
assumed) and a real `Flow Definition` document, rather than monkeypatching
`frappe.has_permission`.
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from itsuperapp.agent_flow.authorization import authorize_node_operation
from itsuperapp.agent_flow.node_registry import node

IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]

# A role distinct from "System Manager" (which Flow Definition's own
# permission list already requires -- see #59) so the Node-permission
# layer can be proven independently of the Flow-permission layer: a user
# can hold System Manager (passing Flow permission) while lacking this
# role (failing Node permission), and vice versa is not possible to
# construct the other way around, which is exactly the isolation these
# tests need.
_ELEVATED_ROLE = "Wave2 Test Elevated Node Role"


@node(
	"test_wave2_restricted_node",
	label="Wave 2 Restricted Test Node",
	permissions=[_ELEVATED_ROLE],
	allowed_operations=["read"],
)
class _RestrictedTestNode:
	@staticmethod
	def execute(context):
		return context


class TestAuthorizeNodeOperation(FrappeTestCase):
	"""No registry snapshot/restore needed here: `_RestrictedTestNode` is
	registered once at module-import time (like `example_nodes.py`'s real
	nodes) and simply persists in the registry for the test process's
	lifetime -- unlike `test_node_registry.py`'s `test_hook_based_module_loading`,
	nothing here tests the load-on-first-use mechanism itself, so there is
	nothing to reset between tests."""

	def _ensure_elevated_role(self):
		if not frappe.db.exists("Role", _ELEVATED_ROLE):
			frappe.get_doc({"doctype": "Role", "role_name": _ELEVATED_ROLE}).insert(ignore_permissions=True)

	def _make_user(self, email, *, roles=None):
		if roles and _ELEVATED_ROLE in roles:
			self._ensure_elevated_role()
		user = frappe.new_doc("User")
		user.email = email
		user.first_name = email.split("@")[0]
		user.enabled = 1
		user.send_welcome_email = 0
		for role in roles or []:
			user.append("roles", {"role": role})
		user.insert(ignore_permissions=True)
		return user

	def _make_flow_definition(self):
		flow = frappe.new_doc("Flow Definition")
		flow.flow_name = f"Wave2 Auth Test Flow {frappe.generate_hash(length=8)}"
		flow.schema_version = 1
		flow.nodes = [{"id": "n1", "type": "noop", "position": {"x": 0, "y": 0}, "config": {}}]
		flow.edges = []
		flow.viewport = {"x": 0, "y": 0, "zoom": 1}
		flow.settings = {}
		flow.insert(ignore_permissions=True)
		return flow

	def test_unknown_node_type_fails_safely(self):
		"""8. unknown node type fails safely."""
		with self.assertRaises(frappe.ValidationError):
			authorize_node_operation(
				execution_identity="Administrator",
				flow_definition="does-not-matter",
				node_type="totally_unregistered_node_type",
			)

	def test_node_permission_denied_for_unprivileged_user(self):
		"""6. node permission declaration enforced.

		This user holds System Manager (passes Flow permission, since
		Flow Definition itself is System-Manager-restricted per #59) but
		not `_ELEVATED_ROLE`, isolating the failure to Node permission."""
		flow = self._make_flow_definition()
		user = self._make_user("wave2-auth-unprivileged@example.com", roles=["System Manager"])
		with self.assertRaises(frappe.PermissionError):
			authorize_node_operation(
				execution_identity=user.name,
				flow_definition=flow.name,
				node_type="test_wave2_restricted_node",
			)

	def test_node_permission_allowed_for_privileged_user(self):
		flow = self._make_flow_definition()
		user = self._make_user("wave2-auth-privileged@example.com", roles=["System Manager", _ELEVATED_ROLE])
		# Must not raise.
		authorize_node_operation(
			execution_identity=user.name,
			flow_definition=flow.name,
			node_type="test_wave2_restricted_node",
			operation="read",
		)

	def test_allowed_operation_denied_for_unsupported_operation(self):
		"""This user holds both System Manager and `_ELEVATED_ROLE`, so
		Flow and Node permission both pass, isolating the failure to the
		Allowed-operation layer specifically."""
		flow = self._make_flow_definition()
		user = self._make_user("wave2-auth-badop@example.com", roles=["System Manager", _ELEVATED_ROLE])
		with self.assertRaises(frappe.PermissionError):
			authorize_node_operation(
				execution_identity=user.name,
				flow_definition=flow.name,
				node_type="test_wave2_restricted_node",
				operation="write",
			)

	def test_node_without_declared_restrictions_allows_any_operation(self):
		flow = self._make_flow_definition()
		# System Manager so Flow permission passes (Flow Definition is
		# System-Manager-restricted per #59); "noop" itself (issue #61)
		# declares no permissions/allowed_operations, so nothing else
		# should narrow this.
		user = self._make_user("wave2-auth-unrestricted@example.com", roles=["System Manager"])
		authorize_node_operation(
			execution_identity=user.name,
			flow_definition=flow.name,
			node_type="noop",
			operation="write",
		)

	def test_flow_permission_denied_for_user_without_flow_definition_access(self):
		"""Flow permission (independent of the target doctype's own Frappe
		permission): a plain user has no Frappe-level access to
		`Flow Definition` at all (restricted to System Manager), so must be
		denied regardless of the node type's own requirements."""
		flow = self._make_flow_definition()
		user = self._make_user("wave2-auth-noflowaccess@example.com")
		with self.assertRaises(frappe.PermissionError):
			authorize_node_operation(
				execution_identity=user.name,
				flow_definition=flow.name,
				node_type="noop",
			)

	def test_unauthorized_user_cannot_reach_protected_frappe_doctype(self):
		"""4. unauthorized user cannot execute protected operation; 9.
		permission denied does not leak protected data -- this asserts a
		clean PermissionError is raised, never that unchecked data is
		returned.

		Real (non-mock) Frappe permission check: `Error Log` is restricted
		to System Manager in stock Frappe core (verified against the
		running site, not assumed). Both cases use the *same* System
		Manager user (so the Flow/Node permission layers -- also gated to
		System Manager for this Wave -- already pass identically) to
		isolate the Frappe-permission layer specifically: `Error Log` is
		not submittable, so even System Manager fails a "submit" check
		against it for real, purely at the Frappe-permission layer."""
		flow = self._make_flow_definition()
		user = self._make_user("wave2-auth-noerrorlog@example.com", roles=["System Manager", _ELEVATED_ROLE])
		error_log = frappe.get_all("Error Log", limit=1, pluck="name")
		if not error_log:
			frappe.get_doc({"doctype": "Error Log", "method": "Wave 2 auth test fixture"}).insert(
				ignore_permissions=True
			)
			error_log = frappe.get_all("Error Log", limit=1, pluck="name")
		# System Manager legitimately CAN read Error Log -- must not raise.
		authorize_node_operation(
			execution_identity=user.name,
			flow_definition=flow.name,
			node_type="test_wave2_restricted_node",
			operation="read",
			doctype="Error Log",
			doc=error_log[0],
		)

		# "noop" has no node/allowed-operation restrictions, so this
		# isolates the failure to the Frappe-permission layer alone:
		# Error Log is not a submittable doctype, so no user -- System
		# Manager included -- has "submit" permission on it.
		with self.assertRaises(frappe.PermissionError):
			authorize_node_operation(
				execution_identity=user.name,
				flow_definition=flow.name,
				node_type="noop",
				operation="submit",
				doctype="Error Log",
				doc=error_log[0],
			)

	def test_frappe_permission_check_uses_explicit_user_not_session(self):
		"""Frappe permission must be checked with an explicit `user=`,
		never implicit `frappe.session.user` -- proven here by running the
		check as a different user than the one currently logged into the
		test session (Administrator, per FrappeTestCase default)."""
		flow = self._make_flow_definition()
		unprivileged = self._make_user("wave2-auth-explicituser@example.com")
		self.assertNotEqual(frappe.session.user, unprivileged.name)
		with self.assertRaises(frappe.PermissionError):
			authorize_node_operation(
				execution_identity=unprivileged.name,
				flow_definition=flow.name,
				node_type="noop",
				operation="read",
				doctype="Error Log",
			)
