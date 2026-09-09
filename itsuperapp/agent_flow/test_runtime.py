"""Tests for the Agent Flow execution runtime (issue #48).

Test fixture node types (registered once at module-import time, like
test_authorization.py's `_RestrictedTestNode` -- never shipped as
production node types) exercise retry/backoff, branching, and the
Waiting/resume contract without needing any of #50's real node catalog.

`execute_flow_run()` is called directly in these tests rather than via
`frappe.enqueue` -- it is not whitelisted (see runtime.py), so calling it
directly is exactly the sanctioned synchronous test/internal-step-
execution helper the design explicitly allows, never a production HTTP
execution path. `resume_flow_run()`'s own internal `frappe.enqueue` call
is likewise not relied upon for test determinism: the resume tests call
`execute_flow_run()` explicitly afterward to continue the walk, so
correctness here doesn't depend on Frappe's test-mode enqueue behavior.
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from itsuperapp.agent_flow.node_registry import node
from itsuperapp.agent_flow.runtime import (
	NodeWaiting,
	cancel_flow_run,
	create_flow_run,
	execute_flow_run,
	resume_flow_run,
)
from itsuperapp.itsuperapp.doctype.flow_run.flow_run import VALID_TRANSITIONS as RUN_TRANSITIONS
from itsuperapp.itsuperapp.doctype.flow_run_step.flow_run_step import (
	VALID_TRANSITIONS as STEP_TRANSITIONS,
)

IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]

_flaky_counters: dict[str, int] = {}


@node(
	"test_wave2_branch_node",
	label="Wave 2 Branch Test Node",
	outputs=[{"name": "out-yes"}, {"name": "out-no"}],
)
class _BranchTestNode:
	@staticmethod
	def execute(context, config):
		port = "out-yes" if config.get("take_yes") else "out-no"
		return {"context": context, "port": port}


@node("test_wave2_flaky_node", label="Wave 2 Flaky Test Node")
class _FlakyTestNode:
	@staticmethod
	def execute(context, config):
		key = config["flaky_key"]
		_flaky_counters[key] = _flaky_counters.get(key, 0) + 1
		if _flaky_counters[key] <= config.get("fail_times", 0):
			raise RuntimeError(f"transient failure #{_flaky_counters[key]}")
		return {"context": context, "port": "out"}


@node("test_wave2_always_fails_node", label="Wave 2 Always Fails Test Node")
class _AlwaysFailsTestNode:
	@staticmethod
	def execute(context, config):
		raise RuntimeError("this node always fails")


@node("test_wave2_waiting_node", label="Wave 2 Waiting Test Node")
class _WaitingTestNode:
	@staticmethod
	def execute(context, config):
		raise NodeWaiting()


class TestFlowRuntime(FrappeTestCase):
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

	def _make_flow(self, nodes, edges, *, settings=None):
		flow = frappe.new_doc("Flow Definition")
		flow.flow_name = f"Wave2 Runtime Test Flow {frappe.generate_hash(length=8)}"
		flow.schema_version = 1
		flow.nodes = nodes
		flow.edges = edges
		flow.viewport = {"x": 0, "y": 0, "zoom": 1}
		flow.settings = settings or {}
		flow.insert(ignore_permissions=True)
		return flow

	def _start(self, flow, *, user, config=None):
		run_name = create_flow_run(
			flow_definition=flow.name,
			config=config or {},
			source="Manual",
			triggering_user=user.name,
		)
		return run_name

	def test_create_run_from_flow_version(self):
		"""1. create Run from Flow Version."""
		user = self._make_user("wave2-rt-create@example.com")
		flow = self._make_flow([{"id": "n1", "type": "noop", "position": {}, "config": {}}], [])
		run_name = self._start(flow, user=user)
		run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(
			run.flow_version, frappe.db.get_value("Flow Version", {"flow_definition": flow.name})
		)
		self.assertEqual(run.execution_identity, user.name)
		self.assertEqual(run.status, "Queued")

	def test_execute_simple_linear_graph_reaches_success(self):
		"""2. execute simple linear graph; 5. successful run reaches SUCCESS."""
		user = self._make_user("wave2-rt-linear@example.com")
		flow = self._make_flow(
			[
				{"id": "n1", "type": "noop", "position": {}, "config": {}},
				{
					"id": "n2",
					"type": "set_variable",
					"position": {},
					"config": {"variable_name": "x", "value": 42},
				},
			],
			[{"id": "e1", "source": "n1", "target": "n2"}],
		)
		run_name = self._start(flow, user=user)
		execute_flow_run(run_name)
		run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(run.status, "Success")
		steps = frappe.get_all(
			"Flow Run Step",
			filters={"flow_run": run_name},
			fields=["node_id", "status"],
			order_by="step_index",
		)
		self.assertEqual([(s.node_id, s.status) for s in steps], [("n1", "Success"), ("n2", "Success")])

	def test_persists_run_step(self):
		"""4. persists Run Step."""
		user = self._make_user("wave2-rt-persist@example.com")
		flow = self._make_flow([{"id": "n1", "type": "noop", "position": {}, "config": {}}], [])
		run_name = self._start(flow, user=user)
		execute_flow_run(run_name)
		step = frappe.get_all(
			"Flow Run Step",
			filters={"flow_run": run_name},
			fields=["node_id", "node_type", "status", "attempt", "step_index"],
		)[0]
		self.assertEqual(step.node_id, "n1")
		self.assertEqual(step.node_type, "noop")
		self.assertEqual(step.status, "Success")
		self.assertEqual(step.attempt, 1)
		self.assertEqual(step.step_index, 0)

	def test_branch_edge_progression(self):
		"""3. branch/edge progression as currently supported."""
		user = self._make_user("wave2-rt-branch@example.com")
		flow = self._make_flow(
			[
				{"id": "n1", "type": "test_wave2_branch_node", "position": {}, "config": {"take_yes": True}},
				{"id": "yes", "type": "noop", "position": {}, "config": {}},
				{"id": "no", "type": "noop", "position": {}, "config": {}},
			],
			[
				{"id": "e1", "source": "n1", "target": "yes", "source_port": "out-yes"},
				{"id": "e2", "source": "n1", "target": "no", "source_port": "out-no"},
			],
		)
		run_name = self._start(flow, user=user)
		execute_flow_run(run_name)
		run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(run.status, "Success")
		executed_nodes = {
			s.node_id
			for s in frappe.get_all("Flow Run Step", filters={"flow_run": run_name}, fields=["node_id"])
		}
		self.assertEqual(executed_nodes, {"n1", "yes"})

	def test_executor_failure_reaches_failed(self):
		"""6. executor failure reaches FAILED."""
		user = self._make_user("wave2-rt-fail@example.com")
		flow = self._make_flow(
			[{"id": "n1", "type": "test_wave2_always_fails_node", "position": {}, "config": {}}], []
		)
		run_name = self._start(flow, user=user)
		execute_flow_run(run_name)
		run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(run.status, "Failed")
		self.assertIn("always fails", run.error)

	def test_retry_succeeds_after_transient_failure(self):
		"""7. retry succeeds after transient failure."""
		user = self._make_user("wave2-rt-retry-ok@example.com")
		flow = self._make_flow(
			[
				{
					"id": "n1",
					"type": "test_wave2_flaky_node",
					"position": {},
					"config": {
						"flaky_key": "retry-ok",
						"fail_times": 2,
						"retry_attempts": 3,
						"retry_delay_ms": 1,
					},
				}
			],
			[],
		)
		run_name = self._start(flow, user=user)
		execute_flow_run(run_name)
		run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(run.status, "Success")
		attempts = sorted(
			s.attempt
			for s in frappe.get_all("Flow Run Step", filters={"flow_run": run_name}, fields=["attempt"])
		)
		self.assertEqual(attempts, [1, 2, 3])

	def test_retry_stops_after_max_attempts(self):
		"""8. retry stops after max attempts."""
		user = self._make_user("wave2-rt-retry-fail@example.com")
		flow = self._make_flow(
			[
				{
					"id": "n1",
					"type": "test_wave2_flaky_node",
					"position": {},
					"config": {
						"flaky_key": "retry-fail",
						"fail_times": 99,
						"retry_attempts": 2,
						"retry_delay_ms": 1,
					},
				}
			],
			[],
		)
		run_name = self._start(flow, user=user)
		execute_flow_run(run_name)
		run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(run.status, "Failed")
		attempts = sorted(
			s.attempt
			for s in frappe.get_all("Flow Run Step", filters={"flow_run": run_name}, fields=["attempt"])
		)
		self.assertEqual(attempts, [1, 2, 3])  # initial + 2 retries, then give up

	def test_waiting_pauses_progression_and_resume_continues(self):
		"""9. WAITING pauses progression; 10. resume continues correctly."""
		user = self._make_user("wave2-rt-wait@example.com")
		flow = self._make_flow(
			[
				{"id": "n1", "type": "test_wave2_waiting_node", "position": {}, "config": {}},
				{"id": "n2", "type": "noop", "position": {}, "config": {}},
			],
			[{"id": "e1", "source": "n1", "target": "n2"}],
		)
		run_name = self._start(flow, user=user)
		execute_flow_run(run_name)
		run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(run.status, "Waiting")
		self.assertEqual(
			frappe.get_all(
				"Flow Run Step", filters={"flow_run": run_name}, pluck="node_id", order_by="creation asc"
			),
			["n1"],
		)

		resume_flow_run(run_name)
		self.assertEqual(frappe.db.get_value("Flow Run", run_name, "status"), "Running")
		execute_flow_run(run_name)  # simulate the enqueued continuation directly, see module docstring

		run.reload()
		self.assertEqual(run.status, "Success")
		self.assertEqual(
			frappe.get_all(
				"Flow Run Step", filters={"flow_run": run_name}, pluck="node_id", order_by="creation asc"
			),
			["n1", "n2"],
		)

	def test_duplicate_replayed_resume_is_rejected(self):
		"""16. duplicate/replayed resume is rejected or idempotent."""
		user = self._make_user("wave2-rt-replay@example.com")
		flow = self._make_flow(
			[{"id": "n1", "type": "test_wave2_waiting_node", "position": {}, "config": {}}], []
		)
		run_name = self._start(flow, user=user)
		execute_flow_run(run_name)
		resume_flow_run(run_name)
		with self.assertRaises(frappe.ValidationError):
			resume_flow_run(run_name)

	def test_cancellation_transition_works(self):
		"""11. cancellation transition works."""
		user = self._make_user("wave2-rt-cancel@example.com")
		flow = self._make_flow([{"id": "n1", "type": "noop", "position": {}, "config": {}}], [])
		run_name = self._start(flow, user=user)
		cancel_flow_run(run_name)
		self.assertEqual(frappe.db.get_value("Flow Run", run_name, "status"), "Cancelled")
		# Idempotent: cancelling an already-Cancelled run is a silent no-op.
		cancel_flow_run(run_name)
		self.assertEqual(frappe.db.get_value("Flow Run", run_name, "status"), "Cancelled")
		# A cancelled run must never actually execute.
		execute_flow_run(run_name)
		self.assertEqual(frappe.get_all("Flow Run Step", filters={"flow_run": run_name}), [])

	def test_live_flow_definition_modification_does_not_affect_active_run(self):
		"""12. live Flow Definition modification does not affect active run."""
		user = self._make_user("wave2-rt-immutable@example.com")
		flow = self._make_flow(
			[
				{
					"id": "n1",
					"type": "set_variable",
					"position": {},
					"config": {"variable_name": "v", "value": "original"},
				}
			],
			[],
		)
		run_name = self._start(flow, user=user)
		original_version = frappe.get_doc("Flow Run", run_name).flow_version

		# Edit the live Flow Definition after the Run was created but before execution.
		flow.reload()
		flow.nodes = [
			{
				"id": "n1",
				"type": "set_variable",
				"position": {},
				"config": {"variable_name": "v", "value": "CHANGED"},
			}
		]
		flow.save()
		self.assertNotEqual(
			frappe.db.get_value(
				"Flow Version", {"flow_definition": flow.name}, "name", order_by="creation desc"
			),
			original_version,
		)

		execute_flow_run(run_name)
		run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(run.flow_version, original_version)
		self.assertEqual(run.status, "Success")
		import json

		self.assertEqual(json.loads(run.output)["v"], "original")

	def test_unknown_node_type_fails_safely(self):
		"""13. unknown node type fails safely."""
		user = self._make_user("wave2-rt-unknown@example.com")
		flow = self._make_flow(
			[{"id": "n1", "type": "totally_unregistered_wave2_node", "position": {}, "config": {}}], []
		)
		run_name = self._start(flow, user=user)
		execute_flow_run(run_name)
		run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(run.status, "Failed")
		self.assertIn("Unknown Agent Flow node type", run.error)

	def test_run_uses_registry_get_executor(self):
		"""14. run uses registry get_executor() -- an unregistered node type
		must fail exactly as get_executor() itself fails (same message),
		proving the runtime resolves nodes through the real registry
		rather than a duplicate lookup."""
		user = self._make_user("wave2-rt-registry@example.com")
		flow = self._make_flow(
			[{"id": "n1", "type": "not_a_real_node_type", "position": {}, "config": {}}], []
		)
		run_name = self._start(flow, user=user)
		execute_flow_run(run_name)
		run = frappe.get_doc("Flow Run", run_name)
		self.assertIn("Unknown Agent Flow node type: not_a_real_node_type", run.error)

	def test_invalid_flow_run_state_transition_rejected(self):
		"""15. invalid state transition rejected (Flow Run)."""
		user = self._make_user("wave2-rt-transition@example.com")
		flow = self._make_flow([{"id": "n1", "type": "noop", "position": {}, "config": {}}], [])
		run_name = self._start(flow, user=user)
		run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(run.status, "Queued")
		run.status = "Success"  # Queued -> Success is not a valid transition
		with self.assertRaises(frappe.ValidationError):
			run.save()

	def test_invalid_flow_run_step_state_transition_rejected(self):
		"""15. invalid state transition rejected (Flow Run Step)."""
		user = self._make_user("wave2-rt-step-transition@example.com")
		flow = self._make_flow([{"id": "n1", "type": "noop", "position": {}, "config": {}}], [])
		run_name = self._start(flow, user=user)
		step = frappe.new_doc("Flow Run Step")
		step.flow_run = run_name
		step.step_index = 0
		step.node_id = "n1"
		step.node_type = "noop"
		step.status = "Success"  # a step may not be *created* directly as Success
		with self.assertRaises(frappe.ValidationError):
			step.insert()

	def test_transition_tables_have_no_impossible_transitions_from_terminal_states(self):
		"""Defensive: every terminal state (empty transition set) really
		allows nothing further, for both Flow Run and Flow Run Step."""
		for table in (RUN_TRANSITIONS, STEP_TRANSITIONS):
			for state, allowed in table.items():
				if state in ("Success", "Failed", "Cancelled", "Skipped"):
					self.assertEqual(allowed, set(), f"{state} must be terminal, got allowed={allowed}")

	def test_max_steps_circuit_breaker_trips(self):
		"""Bonus: the design doc's `settings.max_steps` circuit breaker
		(FlowAgent's ADAPT-rated `max_steps_per_run` pattern) is honored."""
		user = self._make_user("wave2-rt-maxsteps@example.com")
		nodes = [{"id": f"n{i}", "type": "noop", "position": {}, "config": {}} for i in range(5)]
		edges = [{"id": f"e{i}", "source": f"n{i}", "target": f"n{i + 1}"} for i in range(4)]
		flow = self._make_flow(nodes, edges, settings={"max_steps": 2})
		run_name = self._start(flow, user=user)
		execute_flow_run(run_name)
		run = frappe.get_doc("Flow Run", run_name)
		self.assertEqual(run.status, "Failed")
		self.assertIn("max_steps", run.error)
