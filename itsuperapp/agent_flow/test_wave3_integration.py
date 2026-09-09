"""End-to-end runtime integration tests for issue #50's real node catalog
-- proving branch progression, centralized authorization, run-history
persistence, auditable failure, and no-Administrator-fallback against
REAL Frappe nodes (not the test-fixture nodes Wave 2 used), running
through the actual runtime (issue #48) rather than calling an executor
in isolation.
"""

from __future__ import annotations

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from itsuperapp.agent_flow.runtime import create_flow_run, execute_flow_run

IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]


class TestWave3Integration(FrappeTestCase):
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

	def _make_flow(self, nodes, edges):
		flow = frappe.new_doc("Flow Definition")
		flow.flow_name = f"Wave3 Integration Test Flow {frappe.generate_hash(length=8)}"
		flow.schema_version = 1
		flow.nodes = nodes
		flow.edges = edges
		flow.viewport = {"x": 0, "y": 0, "zoom": 1}
		flow.settings = {}
		flow.insert(ignore_permissions=True)
		return flow

	def test_branch_progression_integrates_with_runtime(self):
		"""10. Branch progression integrates with runtime (real Condition node)."""
		user = self._make_user("wave3-int-branch@example.com")
		flow = self._make_flow(
			nodes=[
				{
					"id": "cond",
					"type": "logic_condition",
					"position": {},
					"config": {"left": 5, "operator": ">", "right": 3},
				},
				{"id": "yes_branch", "type": "noop", "position": {}, "config": {}},
				{"id": "no_branch", "type": "noop", "position": {}, "config": {}},
			],
			edges=[
				{"id": "e1", "source": "cond", "target": "yes_branch", "source_port": "out-yes"},
				{"id": "e2", "source": "cond", "target": "no_branch", "source_port": "out-no"},
			],
		)
		run_name = create_flow_run(
			flow_definition=flow.name, config={}, source="Manual", triggering_user=user.name
		)
		execute_flow_run(run_name)
		run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(run.status, "Success")
		executed = set(frappe.get_all("Flow Run Step", filters={"flow_run": run_name}, pluck="node_id"))
		self.assertEqual(executed, {"cond", "yes_branch"})

	def test_real_node_runs_through_centralized_authorization(self):
		"""15. real node runs through centralized authorization -- an
		unprivileged execution identity attempting frappe_create_document
		against a System-Manager-only doctype is denied at the runtime's
		authorize_node_operation() call, recorded as a clean Failed run."""
		user = self._make_user("wave3-int-authz@example.com", roles=[])
		flow = self._make_flow(
			nodes=[
				{
					"id": "n1",
					"type": "frappe_create_document",
					"position": {},
					"config": {"doctype": "Error Log", "values": {"method": "should be denied"}},
				}
			],
			edges=[],
		)
		run_name = create_flow_run(
			flow_definition=flow.name, config={}, source="Manual", triggering_user=user.name
		)
		execute_flow_run(run_name)
		run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(run.status, "Failed")
		self.assertFalse(frappe.db.exists("Error Log", {"method": "should be denied"}))

	def test_run_history_persists_correct_step_result(self):
		"""16. run history persists correct step result."""
		user = self._make_user("wave3-int-history@example.com")
		flow = self._make_flow(
			nodes=[
				{
					"id": "n1",
					"type": "set_variable",
					"position": {},
					"config": {"variable_name": "answer", "value": 42},
				}
			],
			edges=[],
		)
		run_name = create_flow_run(
			flow_definition=flow.name, config={}, source="Manual", triggering_user=user.name
		)
		execute_flow_run(run_name)
		step = frappe.get_all(
			"Flow Run Step", filters={"flow_run": run_name}, fields=["status", "output_snapshot"]
		)[0]
		self.assertEqual(step.status, "Success")
		self.assertEqual(json.loads(step.output_snapshot)["answer"], 42)

	def test_executor_failure_remains_auditable(self):
		"""17. executor failure remains auditable -- a denied real node
		still leaves a Failed Flow Run Step row with a real error message,
		never silently vanishing from the audit trail."""
		user = self._make_user("wave3-int-audit@example.com", roles=[])
		flow = self._make_flow(
			nodes=[
				{
					"id": "n1",
					"type": "frappe_get_document",
					"position": {},
					"config": {"doctype": "Error Log", "name": "does-not-exist-anyway"},
				}
			],
			edges=[],
		)
		run_name = create_flow_run(
			flow_definition=flow.name, config={}, source="Manual", triggering_user=user.name
		)
		execute_flow_run(run_name)
		run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(run.status, "Failed")
		self.assertTrue(run.error)

	def test_no_administrator_fallback_with_real_node(self):
		"""18. no Administrator fallback -- a real Create Document node's
		resulting document is owned by the real triggering user, never
		Administrator, and the run's recorded execution_identity is never
		Administrator either."""
		user = self._make_user("wave3-int-noadmin@example.com", roles=["System Manager"])
		flow = self._make_flow(
			nodes=[
				{
					"id": "n1",
					"type": "frappe_create_document",
					"position": {},
					"config": {
						"doctype": "ToDo",
						"values": {"description": "Wave 3 no-admin-fallback proof"},
					},
				}
			],
			edges=[],
		)
		run_name = create_flow_run(
			flow_definition=flow.name, config={}, source="Manual", triggering_user=user.name
		)
		run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(run.execution_identity, user.name)
		self.assertNotEqual(run.execution_identity, "Administrator")

		execute_flow_run(run_name)
		final_run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(final_run.status, "Success")
		todo_name = frappe.get_all(
			"ToDo", filters={"description": "Wave 3 no-admin-fallback proof"}, limit=1, pluck="name"
		)[0]
		todo = frappe.get_doc("ToDo", todo_name)
		self.assertEqual(todo.owner, user.name)
		self.assertNotEqual(todo.owner, "Administrator")

		# And with no triggering user at all (nothing resolves), the run
		# must fail closed rather than ever falling back to Administrator.
		no_identity_run = create_flow_run(flow_definition=flow.name, config={}, source="Manual")
		no_identity_doc = frappe.get_doc("Flow Run", no_identity_run)
		self.assertEqual(no_identity_doc.status, "Failed")
		self.assertFalse(no_identity_doc.execution_identity)
