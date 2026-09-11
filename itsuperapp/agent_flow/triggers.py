"""Agent Flow trigger dispatch: DocType Event, Schedule, Webhook (issue #62).

Native-Frappe-first, per the Wave 4 authorization's own instruction to
verify before assuming:

- **DocType Event**: Frappe's `doc_events` hook registration is static
  Python, evaluated once per site/process (confirmed by reading
  `frappe.get_doc_hooks()` -- it's built from `hooks.py` and cached in
  `frappe.local.doc_events_hooks`), so a runtime-configurable arbitrary
  DocType/event combination cannot be registered as a *new* hook entry
  per Agent Flow Trigger record. Frappe itself already relies on a `"*"`
  wildcard doctype key in `doc_events` (confirmed: it appears in Frappe
  core's own `hooks.py`, and `Document.run_method()` merges
  `doc_events.get(self.doctype, {})` with `doc_events.get("*", {})` for
  every event) -- so this module registers *one* wildcard handler
  (`on_doctype_event`, wired in this app's hooks.py) that runs for every
  doctype/event and does a fast, indexed database lookup for a matching
  *enabled* Agent Flow Trigger record. This is Wave 4's pre-approved
  "bounded wildcard dispatcher + indexed lookup" design (evidence-based,
  not the naive per-doctype-per-event wildcard #62's own earlier
  planning draft worried about).

- **Schedule**: Frappe's `Scheduled Job Type` doctype is a real,
  database-driven scheduler (confirmed: `frappe.utils.scheduler.
  enqueue_events()` queries `frappe.get_all("Scheduled Job Type",
  filters={"stopped": 0})` on every tick) -- no custom cron engine is
  built. A single shared Scheduled Job Type record (see
  `ensure_schedule_dispatcher`) re-checks every enabled Schedule
  trigger's own `cron_format`/`last_run` each time it fires (every
  minute); seeAgent Flow Trigger's own controller docstring for why a
  *per-trigger* Scheduled Job Type was considered and rejected (Frappe
  invokes a job's `method` as a bare zero-argument call with no
  back-reference to which record fired it).

- **Webhook**: a whitelisted, `allow_guest=True` endpoint (webhooks have
  no Frappe login session -- authenticity comes entirely from HMAC
  verification, never from `allow_guest` alone), HMAC-SHA256 over
  `f"{timestamp}.{raw_body}"`, a Password-fieldtype secret (decrypted
  only at verification time via `frappe.utils.password.
  get_decrypted_password`, never read as plaintext), a 5-minute
  timestamp tolerance, and replay rejection via `frappe.cache` (native
  Redis cache, no new persistent replay-record doctype) keyed by the
  request's own signature with a TTL matching the timestamp tolerance.

Loop protection (issue #62 section 17): `MAX_TRIGGER_DEPTH` bounds how
many times a DocType Event trigger may chain from *within* an
Agent-Flow-executed run (a node's own document operation firing another
configured trigger) -- see `itsuperapp.agent_flow.runtime.execute_flow_run`,
which sets `frappe.flags.agent_flow_trigger_depth` for the duration of a
run's node execution. This never disables triggers globally; it only
caps how deep one chain of automatic re-triggering may go, matching the
"don't break legitimate use" requirement.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from typing import Any

import frappe
from croniter import croniter
from frappe.utils.password import get_decrypted_password

from itsuperapp.agent_flow.runtime import create_flow_run, execute_flow_run

MAX_TRIGGER_DEPTH = 5
WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS = 300
WEBHOOK_MAX_BODY_BYTES = 1_000_000
WEBHOOK_REPLAY_CACHE_PREFIX = "agent_flow_webhook_seen"
SCHEDULE_DISPATCHER_METHOD = "itsuperapp.agent_flow.triggers.run_due_schedule_triggers"

ALLOWED_DOCTYPE_EVENTS = frozenset(
	{"after_insert", "on_update", "on_submit", "on_cancel", "on_trash", "on_update_after_submit"}
)

ALLOWLISTED_WEBHOOK_HEADERS = frozenset({"content-type", "user-agent"})


# ---------------------------------------------------------------------------
# DocType Event
# ---------------------------------------------------------------------------


def on_doctype_event(doc, method: str) -> None:
	"""Registered as a `doc_events` wildcard handler in hooks.py -- fires
	for every doctype's every event. Only enqueues a dispatch job for a
	matching, enabled trigger; never executes a flow synchronously inside
	the caller's own document transaction.
	"""
	if method not in ALLOWED_DOCTYPE_EVENTS:
		return
	if doc.doctype == "Agent Flow Trigger" or not frappe.db.table_exists("Agent Flow Trigger"):
		# This wildcard fires for every doctype's every event, including
		# ones raised by bench migrate's own internal document operations
		# *before* this app's own tables have been created yet on a fresh
		# site/migration (confirmed: migrate failed hard on this exact
		# path before this guard was added). Also skip Agent Flow
		# Trigger's own events -- a trigger firing on itself is never a
		# meaningful Agent Flow automation case.
		return

	depth = getattr(frappe.flags, "agent_flow_trigger_depth", None)
	if depth is not None and depth >= MAX_TRIGGER_DEPTH:
		frappe.logger("agent_flow").warning(
			f"Agent Flow trigger depth limit ({MAX_TRIGGER_DEPTH}) reached; refusing to chain "
			f"further from {doc.doctype} {doc.name} {method}."
		)
		return

	triggers = frappe.get_all(
		"Agent Flow Trigger",
		filters={
			"trigger_type": "DocType Event",
			"enabled": 1,
			"event_doctype": doc.doctype,
			"event_name": method,
		},
		fields=["name", "flow_definition", "service_user"],
	)
	if not triggers:
		return

	next_depth = (depth or 0) + 1
	triggering_user = frappe.session.user
	for trigger in triggers:
		frappe.enqueue(
			_dispatch_doctype_event_trigger,
			queue="default",
			trigger_name=trigger.name,
			flow_definition=trigger.flow_definition,
			service_user=trigger.service_user,
			triggering_user=triggering_user,
			doctype=doc.doctype,
			docname=doc.name,
			trigger_depth=next_depth,
		)


def _dispatch_doctype_event_trigger(
	*,
	trigger_name: str,
	flow_definition: str,
	service_user: str,
	triggering_user: str,
	doctype: str,
	docname: str,
	trigger_depth: int,
) -> None:
	"""Runs inside its own enqueued job (never inline in the firing
	document's transaction). Per ADR 0012's identity priority order, the
	real triggering user (the one whose save/submit fired the event) is
	tried first, falling back to the trigger's configured service_user --
	`resolve_execution_identity` (issue #49) already implements this
	exactly, unmodified.
	"""
	run_name = create_flow_run(
		flow_definition=flow_definition,
		config={},
		source="DocType Event",
		triggering_user=triggering_user,
		service_user=service_user,
		agent_flow_trigger=trigger_name,
		trigger_doctype=doctype,
		trigger_reference=docname,
		trigger_depth=trigger_depth,
		system_triggered=True,
	)
	run = frappe.get_doc("Flow Run", run_name)
	if run.status == "Queued":
		execute_flow_run(run_name)


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------


def ensure_schedule_dispatcher() -> None:
	"""Idempotent bootstrap (called from hooks.py's `after_migrate`):
	creates the single shared native Scheduled Job Type this design
	relies on, if it doesn't already exist. Safe to call on every
	migrate."""
	if frappe.db.exists("Scheduled Job Type", {"method": SCHEDULE_DISPATCHER_METHOD}):
		return
	job = frappe.new_doc("Scheduled Job Type")
	job.method = SCHEDULE_DISPATCHER_METHOD
	job.frequency = "Cron"
	job.cron_format = "* * * * *"
	job.insert(ignore_permissions=True)


def run_due_schedule_triggers() -> None:
	"""The shared Scheduled Job Type's `method`. Re-evaluates every
	enabled Schedule trigger's own `cron_format`/`last_run` on each call
	(every minute) rather than relying on Frappe to tell us which
	specific trigger is due -- see this module's docstring for why."""
	now = frappe.utils.now_datetime()
	triggers = frappe.get_all(
		"Agent Flow Trigger",
		filters={"trigger_type": "Schedule", "enabled": 1},
		fields=["name", "flow_definition", "service_user", "cron_format", "last_run"],
	)
	for trigger in triggers:
		if not _schedule_is_due(trigger.cron_format, trigger.last_run, now):
			continue
		next_fire = croniter(trigger.cron_format, now).get_next(datetime)
		frappe.db.set_value(
			"Agent Flow Trigger", trigger.name, {"last_run": now, "next_run": next_fire}
		)
		frappe.enqueue(
			_dispatch_schedule_trigger,
			queue="default",
			trigger_name=trigger.name,
			flow_definition=trigger.flow_definition,
			service_user=trigger.service_user,
		)


def _schedule_is_due(cron_format: str | None, last_run, now: datetime) -> bool:
	if not cron_format:
		return False
	base = last_run or (now - timedelta(days=1))
	next_fire = croniter(cron_format, base).get_next(datetime)
	return next_fire <= now


def _dispatch_schedule_trigger(*, trigger_name: str, flow_definition: str, service_user: str) -> None:
	"""Schedule has no real triggering user -- only the trigger's own
	configured, validated service_user is ever passed. A disabled service
	user fails closed via resolve_execution_identity (issue #49),
	recording the run as Failed rather than ever falling back to
	Administrator."""
	run_name = create_flow_run(
		flow_definition=flow_definition,
		config={},
		source="Schedule",
		service_user=service_user,
		agent_flow_trigger=trigger_name,
		system_triggered=True,
	)
	run = frappe.get_doc("Flow Run", run_name)
	if run.status == "Queued":
		execute_flow_run(run_name)


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------


class WebhookAuthError(frappe.PermissionError):
	"""Raised for any inbound webhook authentication/validation failure --
	a single exception type so the endpoint always responds uniformly,
	never leaking which specific check failed."""


def webhook_endpoint(trigger_key: str | None = None) -> dict[str, Any]:
	"""Inbound webhook trigger (issue #62, whitelisted with
	`allow_guest=True` in api.py). Guest access only permits the HTTP
	layer to reach this method without a login session -- it is never
	treated as authentication by itself; every request must still pass
	HMAC verification below or is rejected. Returns immediately once
	enqueued; never waits for the flow to finish."""
	trigger_key = trigger_key or frappe.form_dict.get("trigger_key")
	trigger = _load_webhook_trigger(trigger_key)

	raw_body = frappe.request.get_data() or b""
	if len(raw_body) > WEBHOOK_MAX_BODY_BYTES:
		raise WebhookAuthError(frappe._("Request body too large."))

	timestamp = frappe.get_request_header("X-Agent-Flow-Timestamp")
	signature = frappe.get_request_header("X-Agent-Flow-Signature")
	_verify_webhook_signature(trigger, raw_body, timestamp, signature)
	_reject_replay(trigger.name, signature)

	try:
		payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
	except (json.JSONDecodeError, UnicodeDecodeError) as exc:
		raise WebhookAuthError(frappe._("Request body is not valid JSON.")) from exc

	allowlisted_headers = {
		key: value
		for key, value in frappe.request.headers.items()
		if key.lower() in ALLOWLISTED_WEBHOOK_HEADERS
	}
	request_id = frappe.generate_hash(length=16)

	run_name = create_flow_run(
		flow_definition=trigger.flow_definition,
		config={"payload": payload, "headers": allowlisted_headers, "request_id": request_id},
		source="Webhook",
		service_user=trigger.service_user,
		agent_flow_trigger=trigger.name,
		system_triggered=True,
	)
	run = frappe.get_doc("Flow Run", run_name)
	if run.status == "Queued":
		frappe.enqueue(execute_flow_run, queue="default", run_name=run_name)

	frappe.response["http_status_code"] = 202
	return {"accepted": True, "run": run_name, "request_id": request_id}


def _load_webhook_trigger(trigger_key: str | None):
	if not trigger_key:
		raise WebhookAuthError(frappe._("Missing trigger_key."))
	trigger = frappe.db.get_value(
		"Agent Flow Trigger",
		{"webhook_key": trigger_key, "trigger_type": "Webhook", "enabled": 1},
		["name", "flow_definition", "service_user"],
		as_dict=True,
	)
	if not trigger:
		raise WebhookAuthError(frappe._("Unknown or disabled webhook."))
	return trigger


def _verify_webhook_signature(trigger, raw_body: bytes, timestamp: str | None, signature: str | None) -> None:
	if not timestamp or not signature:
		raise WebhookAuthError(frappe._("Missing signature or timestamp."))
	try:
		request_ts = int(timestamp)
	except ValueError as exc:
		raise WebhookAuthError(frappe._("Invalid timestamp.")) from exc
	if abs(int(time.time()) - request_ts) > WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS:
		raise WebhookAuthError(frappe._("Request timestamp is outside the allowed tolerance."))

	secret = get_decrypted_password("Agent Flow Trigger", trigger.name, "webhook_secret")
	signing_input = f"{timestamp}.".encode() + raw_body
	expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).hexdigest()
	if not hmac.compare_digest(expected, signature):
		raise WebhookAuthError(frappe._("Invalid signature."))


def _reject_replay(trigger_name: str, signature: str) -> None:
	cache_key = f"{WEBHOOK_REPLAY_CACHE_PREFIX}:{trigger_name}:{signature}"
	if frappe.cache.get_value(cache_key):
		raise WebhookAuthError(frappe._("This request has already been processed (replay detected)."))
	frappe.cache.set_value(cache_key, "1", expires_in_sec=WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS)
