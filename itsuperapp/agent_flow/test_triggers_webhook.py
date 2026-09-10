"""Tests for Webhook triggers (issue #62): required list items 17-25.

Uses Frappe's own native test utility `frappe.utils.set_request()` (a
thin wrapper over werkzeug's `EnvironBuilder`) to construct a real
request context -- `webhook_endpoint()` reads `frappe.request`/
`frappe.get_request_header()` exactly as it would for a genuine inbound
HTTP call, so this proves the real code path, not a stand-in.

See test_triggers_doctype_event.py's module docstring for why
`frappe.enqueue` is monkeypatched to run synchronously for most of these
tests; test #25 explicitly restores the real (non-synchronous) enqueue
to prove the endpoint does not wait for the flow to finish.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import frappe
from frappe.tests.utils import FrappeTestCase

from itsuperapp.agent_flow.triggers import webhook_endpoint

IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]

WEBHOOK_SECRET = "wave4-test-webhook-secret"


_SYNCHRONOUS_TARGETS = frozenset({"itsuperapp.agent_flow.runtime.execute_flow_run"})


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


def _sign(secret: str, timestamp: str, raw_body: bytes) -> str:
	signing_input = f"{timestamp}.".encode() + raw_body
	return hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).hexdigest()


class TestWebhookTrigger(FrappeTestCase):
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

	def _make_flow(self):
		flow = frappe.new_doc("Flow Definition")
		flow.flow_name = f"Wave4 Webhook Test Flow {frappe.generate_hash(length=8)}"
		flow.schema_version = 1
		flow.nodes = [{"id": "n1", "type": "noop", "position": {}, "config": {}}]
		flow.edges = []
		flow.viewport = {"x": 0, "y": 0, "zoom": 1}
		flow.settings = {}
		flow.insert(ignore_permissions=True)
		return flow

	def _make_trigger(self, flow, *, service_user, secret=WEBHOOK_SECRET):
		return frappe.get_doc(
			{
				"doctype": "Agent Flow Trigger",
				"flow_definition": flow.name,
				"trigger_type": "Webhook",
				"service_user": service_user,
				"webhook_secret": secret,
			}
		).insert(ignore_permissions=True)

	def _send(self, trigger_key, raw_body, *, timestamp=None, signature=None, extra_headers=None):
		timestamp = timestamp if timestamp is not None else str(int(time.time()))
		signature = signature if signature is not None else _sign(WEBHOOK_SECRET, timestamp, raw_body)
		headers = {
			"Content-Type": "application/json",
			"X-Agent-Flow-Timestamp": timestamp,
			"X-Agent-Flow-Signature": signature,
		}
		if extra_headers:
			headers.update(extra_headers)
		frappe.utils.set_request(method="POST", data=raw_body, headers=headers)
		return webhook_endpoint(trigger_key=trigger_key)

	def test_valid_hmac_accepted(self):
		"""17. valid HMAC accepted."""
		user = self._make_user("wave4-webhook-valid@example.com")
		flow = self._make_flow()
		trigger = self._make_trigger(flow, service_user=user.name)
		raw_body = json.dumps({"hello": "world"}).encode()

		result = self._send(trigger.webhook_key, raw_body)

		self.assertTrue(result["accepted"])
		run = frappe.get_doc("Flow Run", result["run"])
		self.assertEqual(run.status, "Success")
		self.assertEqual(run.source, "Webhook")

	def test_invalid_hmac_rejected(self):
		"""18. invalid HMAC rejected."""
		user = self._make_user("wave4-webhook-badhmac@example.com")
		flow = self._make_flow()
		trigger = self._make_trigger(flow, service_user=user.name)
		raw_body = json.dumps({"hello": "world"}).encode()

		with self.assertRaises(frappe.PermissionError):
			self._send(trigger.webhook_key, raw_body, signature="0" * 64)

	def test_missing_signature_rejected(self):
		"""19. missing signature rejected."""
		user = self._make_user("wave4-webhook-missingsig@example.com")
		flow = self._make_flow()
		trigger = self._make_trigger(flow, service_user=user.name)
		raw_body = b"{}"
		timestamp = str(int(time.time()))
		frappe.utils.set_request(method="POST", data=raw_body, headers={"X-Agent-Flow-Timestamp": timestamp})
		with self.assertRaises(frappe.PermissionError):
			webhook_endpoint(trigger_key=trigger.webhook_key)

	def test_expired_timestamp_rejected(self):
		"""20. expired timestamp rejected."""
		user = self._make_user("wave4-webhook-expired@example.com")
		flow = self._make_flow()
		trigger = self._make_trigger(flow, service_user=user.name)
		raw_body = b"{}"
		old_timestamp = str(int(time.time()) - 3600)

		with self.assertRaises(frappe.PermissionError):
			self._send(trigger.webhook_key, raw_body, timestamp=old_timestamp)

	def test_replay_rejected(self):
		"""21. replay rejected/idempotent -- the exact same signed request,
		submitted twice, is accepted once and rejected the second time."""
		user = self._make_user("wave4-webhook-replay@example.com")
		flow = self._make_flow()
		trigger = self._make_trigger(flow, service_user=user.name)
		raw_body = json.dumps({"n": 1}).encode()
		timestamp = str(int(time.time()))
		signature = _sign(WEBHOOK_SECRET, timestamp, raw_body)

		self._send(trigger.webhook_key, raw_body, timestamp=timestamp, signature=signature)
		with self.assertRaises(frappe.PermissionError):
			self._send(trigger.webhook_key, raw_body, timestamp=timestamp, signature=signature)

	def test_oversized_request_rejected(self):
		"""22. oversized request rejected."""
		user = self._make_user("wave4-webhook-oversized@example.com")
		flow = self._make_flow()
		trigger = self._make_trigger(flow, service_user=user.name)
		raw_body = b"x" * (1_000_000 + 1)

		with self.assertRaises(frappe.PermissionError):
			self._send(trigger.webhook_key, raw_body)

	def test_service_user_comes_only_from_trusted_config(self):
		"""23. service user comes only from trusted config; 24. caller
		cannot inject execution identity -- a payload-supplied
		"service_user"/"execution_identity" field is inert; the run's
		real execution identity is always the trigger's own configured
		service_user."""
		user = self._make_user("wave4-webhook-trusted@example.com")
		attacker_user = self._make_user("wave4-webhook-attacker@example.com")
		flow = self._make_flow()
		trigger = self._make_trigger(flow, service_user=user.name)
		raw_body = json.dumps(
			{"service_user": attacker_user.name, "execution_identity": "Administrator"}
		).encode()

		result = self._send(trigger.webhook_key, raw_body)

		run = frappe.get_doc("Flow Run", result["run"])
		self.assertEqual(run.execution_identity, user.name)
		self.assertNotEqual(run.execution_identity, attacker_user.name)
		self.assertNotEqual(run.execution_identity, "Administrator")

	def test_endpoint_returns_without_waiting_for_flow_completion(self):
		"""25. endpoint returns without waiting for flow completion --
		restores the *real* frappe.enqueue (not the synchronous test
		monkeypatch) so the created Flow Run is still Queued immediately
		after the endpoint returns, proving the response doesn't wait."""
		frappe.enqueue = self._original_enqueue
		user = self._make_user("wave4-webhook-async@example.com")
		flow = self._make_flow()
		trigger = self._make_trigger(flow, service_user=user.name)
		raw_body = b"{}"

		result = self._send(trigger.webhook_key, raw_body)

		run = frappe.get_doc("Flow Run", result["run"])
		self.assertEqual(run.status, "Queued")

	def test_unknown_webhook_key_rejected(self):
		with self.assertRaises(frappe.PermissionError):
			self._send("totally-unknown-key", b"{}")

	def test_webhook_secret_never_appears_in_error_messages(self):
		"""Security: an invalid-signature error must not leak the secret."""
		user = self._make_user("wave4-webhook-noleaksecret@example.com")
		flow = self._make_flow()
		trigger = self._make_trigger(flow, service_user=user.name)
		raw_body = b"{}"
		try:
			self._send(trigger.webhook_key, raw_body, signature="0" * 64)
		except frappe.PermissionError as exc:
			self.assertNotIn(WEBHOOK_SECRET, str(exc))
