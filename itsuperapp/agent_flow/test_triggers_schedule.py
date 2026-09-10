"""Tests for Schedule triggers (issue #62): required list items 12-16.

See test_triggers_doctype_event.py's module docstring for why
`frappe.enqueue` is monkeypatched to run synchronously in these tests.
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from itsuperapp.agent_flow.triggers import run_due_schedule_triggers

IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]


_SYNCHRONOUS_TARGETS = frozenset(
	{
		"itsuperapp.agent_flow.triggers._dispatch_schedule_trigger",
		"itsuperapp.agent_flow.runtime.execute_flow_run",
	}
)


def _make_synchronous_enqueue(original_enqueue):
	def _enqueue(method, queue="default", **kwargs):
		name = method if isinstance(method, str) else f"{method.__module__}.{method.__qualname__}"
		if name in _SYNCHRONOUS_TARGETS:
			fn = frappe.get_attr(name) if isinstance(method, str) else method
			return fn(**kwargs)
		# Anything else must go through the real enqueue -- see
		# test_triggers_doctype_event.py's module docstring for why an
		# unconditional blanket monkeypatch is unsafe.
		return original_enqueue(method, queue=queue, **kwargs)

	return _enqueue


class TestScheduleTrigger(FrappeTestCase):
	def setUp(self):
		self._original_enqueue = frappe.enqueue
		frappe.enqueue = _make_synchronous_enqueue(self._original_enqueue)
		self.addCleanup(lambda: setattr(frappe, "enqueue", self._original_enqueue))

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
		flow.flow_name = f"Wave4 Schedule Test Flow {frappe.generate_hash(length=8)}"
		flow.schema_version = 1
		flow.nodes = [{"id": "n1", "type": "noop", "position": {}, "config": {}}]
		flow.edges = []
		flow.viewport = {"x": 0, "y": 0, "zoom": 1}
		flow.settings = {}
		flow.insert(ignore_permissions=True)
		return flow

	def _make_trigger(self, flow, *, service_user, cron_format="* * * * *", enabled=1):
		return frappe.get_doc(
			{
				"doctype": "Agent Flow Trigger",
				"flow_definition": flow.name,
				"enabled": enabled,
				"trigger_type": "Schedule",
				"service_user": service_user,
				"cron_format": cron_format,
			}
		).insert(ignore_permissions=True)

	def test_valid_schedule_accepted_and_due_execution_enqueues_flow(self):
		"""12. valid schedule accepted; 14. scheduled execution enqueues
		flow -- a never-yet-run, every-minute trigger is immediately due."""
		user = self._make_user("wave4-schedule-due@example.com")
		flow = self._make_flow()
		trigger = self._make_trigger(flow, service_user=user.name)

		run_due_schedule_triggers()

		runs = frappe.get_all(
			"Flow Run", filters={"agent_flow_trigger": trigger.name}, fields=["status", "source"]
		)
		self.assertEqual(len(runs), 1)
		self.assertEqual(runs[0].status, "Success")
		self.assertEqual(runs[0].source, "Schedule")
		self.assertIsNotNone(frappe.db.get_value("Agent Flow Trigger", trigger.name, "last_run"))

	def test_not_yet_due_trigger_is_skipped(self):
		"""Complements #14: a trigger whose cron says "once a year, and
		last ran a second ago" is correctly *not* due right now."""
		user = self._make_user("wave4-schedule-notdue@example.com")
		flow = self._make_flow()
		trigger = self._make_trigger(flow, service_user=user.name, cron_format="0 0 1 1 *")
		frappe.db.set_value("Agent Flow Trigger", trigger.name, "last_run", frappe.utils.now_datetime())

		run_due_schedule_triggers()

		runs = frappe.get_all("Flow Run", filters={"agent_flow_trigger": trigger.name})
		self.assertEqual(runs, [])

	def test_disabled_trigger_skipped(self):
		"""15. disabled trigger skipped."""
		user = self._make_user("wave4-schedule-disabled@example.com")
		flow = self._make_flow()
		trigger = self._make_trigger(flow, service_user=user.name, enabled=0)

		run_due_schedule_triggers()

		runs = frappe.get_all("Flow Run", filters={"agent_flow_trigger": trigger.name})
		self.assertEqual(runs, [])

	def test_disabled_service_user_fails_closed(self):
		"""16. disabled service user fails closed -- never silently runs
		as Administrator. The trigger's service_user was valid at save
		time; disabling the user afterwards (a real-world scenario:
		someone deactivates an account later) must still be caught at
		dispatch time, recorded as a clean Failed run."""
		user = self._make_user("wave4-schedule-svcdisabled@example.com")
		flow = self._make_flow()
		trigger = self._make_trigger(flow, service_user=user.name)
		frappe.db.set_value("User", user.name, "enabled", 0)

		run_due_schedule_triggers()

		runs = frappe.get_all(
			"Flow Run", filters={"agent_flow_trigger": trigger.name}, fields=["status", "execution_identity"]
		)
		self.assertEqual(len(runs), 1)
		self.assertEqual(runs[0].status, "Failed")
		self.assertFalse(runs[0].execution_identity)
		self.assertNotEqual(runs[0].execution_identity, "Administrator")

	def test_deleting_referenced_flow_definition_is_blocked_by_native_link_integrity(self):
		"""Section 18's "deleted flow" case: Frappe's own Link-integrity
		check (not custom code) prevents deleting a Flow Definition that
		an Agent Flow Trigger still references."""
		user = self._make_user("wave4-schedule-linkintegrity@example.com")
		flow = self._make_flow()
		self._make_trigger(flow, service_user=user.name)

		with self.assertRaises(frappe.LinkExistsError):
			frappe.delete_doc("Flow Definition", flow.name, ignore_permissions=True)
