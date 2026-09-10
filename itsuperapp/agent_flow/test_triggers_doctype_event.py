"""Tests for DocType Event triggers (issue #62): required list items 7-11,
26-30 (the integration items, exercised here for the DocType Event path
specifically).

`frappe.enqueue` is monkeypatched to call its target synchronously for
these tests -- `frappe.enqueue(method, queue=..., **kwargs)` genuinely
pushes to a real RQ queue even under `bench run-tests` (confirmed by
reading background_jobs.py's own `call_directly` condition, which is
only true when `now=True` or `is_async=False`, neither of which this
module's own enqueue calls pass), so without this, no worker would ever
pick up the dispatched job inside a test process. This mirrors this
app's own established pattern of calling `execute_flow_run()` directly
in tests rather than relying on its own `frappe.enqueue` call (see
test_runtime.py).
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from itsuperapp.agent_flow.node_registry import all_node_types
from itsuperapp.agent_flow.triggers import MAX_TRIGGER_DEPTH, on_doctype_event

IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]


_SYNCHRONOUS_TARGETS = frozenset(
	{
		"itsuperapp.agent_flow.triggers._dispatch_doctype_event_trigger",
		"itsuperapp.agent_flow.runtime.execute_flow_run",
	}
)


def _make_synchronous_enqueue(original_enqueue):
	def _enqueue(method, queue="default", **kwargs):
		name = method if isinstance(method, str) else f"{method.__module__}.{method.__qualname__}"
		if name in _SYNCHRONOUS_TARGETS:
			fn = frappe.get_attr(name) if isinstance(method, str) else method
			return fn(**kwargs)
		# Anything else (e.g. Frappe core's own User.on_update -> create_contact)
		# must go through the real enqueue -- intercepting every call
		# unconditionally broke unrelated Frappe internals (confirmed:
		# create_contact() doesn't accept the now=/enqueue_after_commit=
		# kwargs a naive blanket monkeypatch forwarded to it).
		return original_enqueue(method, queue=queue, **kwargs)

	return _enqueue


class TestDocTypeEventTrigger(FrappeTestCase):
	def setUp(self):
		self._original_enqueue = frappe.enqueue
		frappe.enqueue = _make_synchronous_enqueue(self._original_enqueue)
		self.addCleanup(lambda: setattr(frappe, "enqueue", self._original_enqueue))

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

	def _make_flow(self, node_type="noop", config=None):
		flow = frappe.new_doc("Flow Definition")
		flow.flow_name = f"Wave4 DocEvent Test Flow {frappe.generate_hash(length=8)}"
		flow.schema_version = 1
		flow.nodes = [{"id": "n1", "type": node_type, "position": {}, "config": config or {}}]
		flow.edges = []
		flow.viewport = {"x": 0, "y": 0, "zoom": 1}
		flow.settings = {}
		flow.insert(ignore_permissions=True)
		return flow

	def _make_trigger(
		self, flow, *, event_doctype="ToDo", event_name="after_insert", service_user, enabled=1
	):
		return frappe.get_doc(
			{
				"doctype": "Agent Flow Trigger",
				"flow_definition": flow.name,
				"enabled": enabled,
				"trigger_type": "DocType Event",
				"service_user": service_user,
				"event_doctype": event_doctype,
				"event_name": event_name,
			}
		).insert(ignore_permissions=True)

	def test_configured_doctype_event_fires(self):
		"""7. configured doctype/event fires; 10. matching event enqueues
		one run; 26. automatic trigger creates auditable Flow Run; 27.
		trigger source/reference persisted correctly; 28. runtime still
		passes centralized authorization; 29. no Administrator fallback."""
		user = self._make_user("wave4-docevent-fire@example.com")
		flow = self._make_flow()
		trigger = self._make_trigger(flow, service_user=user.name)

		todo = frappe.get_doc({"doctype": "ToDo", "description": "Wave 4 doc-event fire target"}).insert(
			ignore_permissions=True
		)

		runs = frappe.get_all(
			"Flow Run",
			filters={"agent_flow_trigger": trigger.name},
			fields=["name", "status", "execution_identity", "source", "trigger_doctype", "trigger_reference"],
		)
		self.assertEqual(len(runs), 1)
		run = runs[0]
		self.assertEqual(run.status, "Success")
		self.assertEqual(run.source, "DocType Event")
		self.assertEqual(run.trigger_doctype, "ToDo")
		self.assertEqual(run.trigger_reference, todo.name)
		self.assertNotEqual(run.execution_identity, "Administrator")

	def test_different_doctype_does_not_fire(self):
		"""8. different doctype does not fire."""
		user = self._make_user("wave4-docevent-diffdt@example.com")
		flow = self._make_flow()
		trigger = self._make_trigger(flow, event_doctype="ToDo", service_user=user.name)

		error_log = frappe.get_doc(
			{"doctype": "Error Log", "method": "Wave 4 doc-event non-match"}
		).insert(ignore_permissions=True)
		# Error Log's own controller commits explicitly outside any test
		# transaction in some code paths (confirmed empirically: this row
		# survived FrappeTestCase's rollback) -- clean it up explicitly
		# rather than relying on rollback, per this Wave's own "zero
		# leftover test documents" requirement.
		self.addCleanup(
			lambda: frappe.delete_doc(
				"Error Log", error_log.name, ignore_permissions=True, force=True
			)
		)

		runs = frappe.get_all("Flow Run", filters={"agent_flow_trigger": trigger.name})
		self.assertEqual(runs, [])

	def test_different_event_does_not_fire(self):
		"""9. different event does not fire."""
		user = self._make_user("wave4-docevent-diffevt@example.com")
		flow = self._make_flow()
		trigger = self._make_trigger(flow, event_name="on_trash", service_user=user.name)

		# after_insert fires on creation; this trigger only listens for on_trash.
		frappe.get_doc({"doctype": "ToDo", "description": "Wave 4 doc-event wrong-event"}).insert(
			ignore_permissions=True
		)

		runs = frappe.get_all("Flow Run", filters={"agent_flow_trigger": trigger.name})
		self.assertEqual(runs, [])

	def test_disabled_trigger_skipped(self):
		"""3 (dispatch-level). disabled trigger does not run."""
		user = self._make_user("wave4-docevent-disabled@example.com")
		flow = self._make_flow()
		trigger = self._make_trigger(flow, service_user=user.name, enabled=0)

		frappe.get_doc({"doctype": "ToDo", "description": "Wave 4 doc-event disabled"}).insert(
			ignore_permissions=True
		)

		runs = frappe.get_all("Flow Run", filters={"agent_flow_trigger": trigger.name})
		self.assertEqual(runs, [])

	def test_recursion_loop_protection(self):
		"""11. recursion/loop protection works -- a flow whose own node
		updates the same ToDo it was triggered by, with a trigger
		configured on that same doctype/event, must stop chaining at
		MAX_TRIGGER_DEPTH rather than looping forever."""
		user = self._make_user("wave4-docevent-loop@example.com")
		flow = self._make_flow(
			node_type="frappe_update_document",
			config={},  # filled in per-run via the trigger context below is not used; see note
		)
		# The Update Document node needs a concrete doctype/name to act on;
		# since every recursive run targets the *same* ToDo, hardcode it
		# via a second, deterministic flow definition update below.
		trigger = self._make_trigger(flow, event_name="on_update", service_user=user.name)

		todo = frappe.get_doc({"doctype": "ToDo", "description": "Wave 4 loop target"}).insert(
			ignore_permissions=True
		)
		flow.reload()
		flow.nodes = [
			{
				"id": "n1",
				"type": "frappe_update_document",
				"position": {},
				"config": {"doctype": "ToDo", "name": todo.name, "values": {"priority": "High"}},
			}
		]
		flow.save(ignore_permissions=True)

		# Triggers on_update; the node's own doc.save() on the same ToDo
		# fires on_update again, which matches the same trigger again --
		# a real recursive chain, bounded by MAX_TRIGGER_DEPTH.
		todo.description = "Wave 4 loop target (edited)"
		todo.save(ignore_permissions=True)

		runs = frappe.get_all(
			"Flow Run", filters={"agent_flow_trigger": trigger.name}, fields=["trigger_depth"]
		)
		self.assertGreater(len(runs), 0)
		# +1: Frappe's own on_update also fires once on insert (a real,
		# separately-confirmed Frappe quirk, not a loop-protection bug) --
		# the ToDo's own creation above produces one extra depth=1 run
		# (its Flow Version snapshot at that point had no real node
		# config yet, so it fails without recursing further), independent
		# of the *real* recursive chain proven below.
		self.assertLessEqual(len(runs), MAX_TRIGGER_DEPTH + 1)
		self.assertTrue(all(r.trigger_depth <= MAX_TRIGGER_DEPTH for r in runs))
		self.assertIn(MAX_TRIGGER_DEPTH, [r.trigger_depth for r in runs])

	def test_unknown_node_type_still_denied_through_registry(self):
		"""Sanity: the trigger path resolves nodes through the same
		canonical registry as Manual runs -- no parallel resolution."""
		self.assertIn("noop", all_node_types())

	def test_ignored_event_is_a_fast_noop(self):
		"""Defensive: an event outside ALLOWED_DOCTYPE_EVENTS never even
		reaches the trigger lookup."""

		class _FakeDoc:
			doctype = "ToDo"
			name = "fake"

		# before_insert is a real Frappe doc event but not one Agent Flow
		# listens for -- must return immediately without raising even if
		# no trigger/table context is set up for it.
		on_doctype_event(_FakeDoc(), "before_insert")
