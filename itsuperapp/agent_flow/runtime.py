"""Agent Flow execution runtime (issue #48).

Per docs/architecture/agent-flow-design.md -> "Execution Model":

    Trigger
      -> Load Flow Version (immutable snapshot at trigger time)
      -> Create Run (status=Queued, execution_identity resolved+recorded)
      -> Resolve Execution Identity (fail closed -- itsuperapp.agent_flow.identity)
      -> Resolve Node (via the canonical registry, get_executor())
      -> Permission Check (itsuperapp.agent_flow.authorization, centralized)
      -> Execute (always via frappe.enqueue, never inside an HTTP request)
      -> Persist Step (commit after every step, not only at run end)
      -> Resolve Next Edge (port-filtered -- supports branching)
      -> Continue / Wait (human approval, resumed by resume_flow_run) / Finish

Executor contract (completed here for issue #61's noop/set_variable
stubs, which explicitly deferred this to #48): `execute(context, config)`
returns `{"context": <dict>, "port": <str, default "out">}`, or raises
`NodeWaiting` to pause the run, or raises any other exception to signal
failure (subject to retry/on_error policy).

Only a Manual trigger is wired in Wave 2 (`start_flow_run`, the Manual
Run API). `source`/`trigger_doctype`/`trigger_reference` are schema-
complete for DocType Event/Schedule/Webhook (per the design doc's Flow
Run field list), but no real `doc_events`/`scheduler_events` hook wiring
is added -- that needs an actual Trigger-configuration mechanism (which
field/UI on Flow Definition chooses the DocType/event/cron) that doesn't
exist yet and is not part of #48/#49's scope. `create_flow_run()` is
already trigger-source-agnostic so that future wiring is a hook
registration calling this same function, not a rewrite.

Cancellation is cooperative, not preemptive (Wave 2's minimal-correct
semantics per the design's cancellation risk note): a Running walk
re-reads its own Flow Run's status fresh from the database before
executing each node and stops immediately, without executing further
nodes, if it observes Cancelled. There is no cross-process interrupt of
an in-flight node execution itself.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from typing import Any

import frappe

from itsuperapp.agent_flow.authorization import authorize_node_operation
from itsuperapp.agent_flow.identity import resolve_execution_identity
from itsuperapp.agent_flow.node_registry import all_node_types, get_executor
from itsuperapp.itsuperapp.doctype.flow_version.flow_version import as_obj

DEFAULT_MAX_STEPS = 100
DEFAULT_RETRY_ATTEMPTS = 0
DEFAULT_RETRY_DELAY_MS = 0
MAX_RETRY_DELAY_MS = 30_000
MAX_RETRY_ATTEMPTS = 10  # bounds a node config's own retry_attempts -- a runaway-retry circuit breaker
RESUMABLE_ROLES = frozenset({"System Manager"})
DEFAULT_APPROVAL_EXPIRY_HOURS = 72


class NodeWaiting(Exception):
	"""Raised by an executor to pause the run (e.g. pending human approval).

	Plain `NodeWaiting()` (no args) gets the generic Wave 2 contract: the
	step/run pause as Waiting, resumable only by `resume_flow_run()`
	(execution identity or System Manager, no token).

	`NodeWaiting(approver=..., subject=...)` additionally requests issue
	#50's secure Human Approval flow: the runtime generates a
	cryptographically random, single-use, run/step-scoped token (never
	stored in plaintext -- only its sha256 hash), notifies `approver` via
	Frappe's native Notification Log with a resume link carrying the
	token, and the run becomes resumable via `resume_flow_run_with_token()`
	-- token possession is itself the authorization for that specific
	action, independent of the caller's own roles.
	"""

	def __init__(
		self,
		*,
		approver: str | None = None,
		subject: str | None = None,
		expires_in_hours: int = DEFAULT_APPROVAL_EXPIRY_HOURS,
	):
		super().__init__("Flow Run paused, awaiting resume.")
		self.approver = approver
		self.subject = subject or "Flow Run awaiting your approval"
		self.expires_in_hours = expires_in_hours


def start_flow_run(flow_definition: str, config: dict | str | None = None) -> str:
	"""Manual Run API (whitelisted in api.py). Enqueues execution and
	returns immediately -- never runs the workflow synchronously inside
	this HTTP request."""
	config = as_obj(config) or {}
	triggering_user = frappe.session.user
	run_name = create_flow_run(
		flow_definition=flow_definition,
		config=config,
		source="Manual",
		triggering_user=triggering_user,
	)
	run = frappe.get_doc("Flow Run", run_name)
	if run.status == "Queued":
		frappe.enqueue(execute_flow_run, queue="default", run_name=run_name)
	return run_name


def create_flow_run(
	*,
	flow_definition: str,
	config: dict,
	source: str,
	triggering_user: str | None = None,
	service_user: str | None = None,
	configured_user: str | None = None,
) -> str:
	"""Create a Flow Run against the *latest* Flow Version of `flow_definition`
	and resolve its execution identity, recording it either way. Fails
	closed: if no identity resolves, the run is created directly as
	Failed with an explicit error, never started, per the Security Model.
	"""
	flow_version_name = _latest_flow_version(flow_definition)
	execution_identity = resolve_execution_identity(
		triggering_user=triggering_user,
		service_user=service_user,
		configured_user=configured_user,
	)

	run = frappe.new_doc("Flow Run")
	run.flow_version = flow_version_name
	run.source = source
	run.config_snapshot = json.dumps(config, sort_keys=True)
	run.input = json.dumps(config, sort_keys=True)
	run.status = "Queued"
	if execution_identity:
		run.execution_identity = execution_identity
	run.insert()

	if not execution_identity:
		_transition_run(
			run,
			"Failed",
			error=frappe._("No execution identity configured; refusing to run."),
			finished_at=frappe.utils.now_datetime(),
		)
	return run.name


def _latest_flow_version(flow_definition: str) -> str:
	version = frappe.db.get_value(
		"Flow Version",
		{"flow_definition": flow_definition},
		"name",
		order_by="creation desc",
	)
	if not version:
		frappe.throw(
			frappe._("Flow Definition {0} has no Flow Version snapshot yet.").format(flow_definition)
		)
	return version


def execute_flow_run(run_name: str) -> None:
	"""Worker entry point (enqueued, never whitelisted -- this must never
	become an HTTP execution path). Walks the graph from wherever this
	run's Flow Run Step history says it left off (empty history = fresh
	start; a Waiting step = resume)."""
	run = frappe.get_doc("Flow Run", run_name)
	if run.status not in ("Queued", "Running"):
		return  # already terminal/cancelled -- nothing to do

	flow_version = frappe.get_doc("Flow Version", run.flow_version)
	nodes = {n["id"]: n for n in as_obj(flow_version.nodes) or []}
	edges = as_obj(flow_version.edges) or []
	settings = as_obj(flow_version.settings) or {}

	if run.status == "Queued":
		_transition_run(run, "Running", started_at=frappe.utils.now_datetime())
		pending = _entry_nodes(nodes, edges)
		context = as_obj(run.input) or {}
	else:
		pending, context = _resume_state(run, nodes, edges)

	original_user = frappe.session.user
	try:
		frappe.set_user(run.execution_identity)
		_walk(run, flow_version, nodes, edges, settings, pending, context)
	finally:
		frappe.set_user(original_user)


def _entry_nodes(nodes: dict, edges: list) -> list[str]:
	targets = {e["target"] for e in edges}
	return [node_id for node_id in nodes if node_id not in targets]


def _resume_state(run, nodes: dict, edges: list) -> tuple[list[str], dict]:
	waiting_step_name = frappe.db.get_value(
		"Flow Run Step",
		{"flow_run": run.name, "status": "Waiting"},
		"name",
		order_by="creation desc",
	)
	context = as_obj(run.output) or as_obj(run.input) or {}
	if not waiting_step_name:
		return [], context
	waiting_step = frappe.get_doc("Flow Run Step", waiting_step_name)
	node_id = waiting_step.node_id
	waiting_step.status = "Success"
	waiting_step.finished_at = frappe.utils.now_datetime()
	waiting_step.save(ignore_permissions=True)  # bookkeeping write -- see _create_step's docstring
	pending = _next_nodes(edges, node_id, "out")
	return pending, context


def _next_nodes(edges: list, source_node_id: str, port: str) -> list[str]:
	targets = []
	for edge in edges:
		if edge.get("source") != source_node_id:
			continue
		edge_port = edge.get("source_port") or "out"
		if edge_port == port:
			targets.append(edge["target"])
	return targets


def _walk(
	run, flow_version, nodes: dict, edges: list, settings: dict, pending: list[str], context: dict
) -> None:
	max_steps = settings.get("max_steps") or DEFAULT_MAX_STEPS
	on_error = settings.get("on_error") or "Stop"
	step_index = frappe.db.count("Flow Run Step", {"flow_run": run.name})
	visited: set[str] = set()

	while pending:
		if step_index >= max_steps:
			_transition_run(
				run,
				"Failed",
				error=frappe._("Exceeded max_steps ({0}); circuit breaker tripped.").format(max_steps),
				finished_at=frappe.utils.now_datetime(),
			)
			return
		if _is_cancelled(run.name):
			return  # cooperative cancellation: stop, leave status as Cancelled

		node_id = pending.pop(0)
		if node_id in visited or node_id not in nodes:
			continue
		visited.add(node_id)
		node = nodes[node_id]

		try:
			port, context = _execute_node_with_retry(run, flow_version, node, step_index, context)
		except NodeWaiting:
			_transition_run(run, "Waiting")
			return
		except Exception as exc:  # node failures are data, not bugs to propagate
			step_index += 1
			if on_error == "Continue":
				continue
			_transition_run(run, "Failed", error=str(exc), finished_at=frappe.utils.now_datetime())
			return
		step_index += 1
		pending.extend(_next_nodes(edges, node_id, port))

	run.reload()
	if run.status == "Running":
		_transition_run(
			run,
			"Success",
			output=json.dumps(context, sort_keys=True),
			finished_at=frappe.utils.now_datetime(),
		)


def _node_operation(node_type: str) -> str:
	"""Derive the operation to check at the centralized authorization gate
	from the node type's own registered `allowed_operations` (issue #50):
	a node with exactly one declared operation (e.g. `frappe_create_document`
	-> "create") is checked against that operation specifically, so the
	Frappe-permission layer below is meaningful for it. A node with no
	declared operations (e.g. `noop`, `logic_condition`) -- or, in
	principle, more than one -- falls back to the generic "execute",
	which every empty-`allowed_operations` node trivially satisfies.
	"""
	allowed = (all_node_types().get(node_type) or {}).get("allowed_operations") or []
	return allowed[0] if len(allowed) == 1 else "execute"


def _execute_node_with_retry(
	run, flow_version, node: dict, step_index: int, context: dict
) -> tuple[str, dict]:
	node_type = node["type"]
	config = node.get("config") or {}
	authorize_node_operation(
		execution_identity=run.execution_identity,
		flow_definition=flow_version.flow_definition,
		node_type=node_type,
		operation=_node_operation(node_type),
		doctype=config.get("doctype"),
		doc=config.get("name"),
	)
	executor = get_executor(node_type)
	retry_attempts = min(config.get("retry_attempts", DEFAULT_RETRY_ATTEMPTS), MAX_RETRY_ATTEMPTS)
	retry_delay_ms = config.get("retry_delay_ms", DEFAULT_RETRY_DELAY_MS)

	last_error: Exception | None = None
	for attempt in range(1, retry_attempts + 2):  # +1 for the initial try, +1 for range's exclusive end
		step = _create_step(run, node, step_index, attempt, context)
		started = time.monotonic()
		try:
			result = executor.execute(dict(context), config)
		except NodeWaiting as waiting:
			_finish_step(step, "Waiting", started, output=None, error=None)
			if waiting.approver:
				_create_approval_token(step, waiting)
			raise
		except Exception as exc:  # classify as a retryable node failure
			last_error = exc
			_finish_step(step, "Failed", started, output=None, error=str(exc))
			if attempt <= retry_attempts:
				delay = min(retry_delay_ms * (2 ** (attempt - 1)), MAX_RETRY_DELAY_MS)
				if delay:
					time.sleep(delay / 1000)
				continue
			raise
		new_context = result.get("context", context)
		port = result.get("port", "out")
		_finish_step(step, "Success", started, output=new_context, error=None)
		return port, new_context

	raise last_error  # pragma: no cover -- loop always returns or raises above


def _create_step(run, node: dict, step_index: int, attempt: int, context: dict):
	"""Bookkeeping write. `_create_step`/`_finish_step`/`_transition_run`/
	`_resume_state`'s Flow Run Step save all use `ignore_permissions=True`
	deliberately: these are the *runtime's own* framework-owned audit-
	trail records (analogous to Frappe's own internal Error Log/Version
	writes), not a node's business-document operation -- the distinction
	the "never ignore_permissions" rule in ADR 0012's Security Model is
	about. A node's own Frappe operations (Create/Update/Submit/Read,
	Assignment, Notification, Workflow Action) never bypass permissions;
	only recording that a step ran (or failed) does.

	This matters concretely: an execution identity can legitimately be a
	low-privileged user with no access to the Flow Run/Flow Run Step
	doctypes themselves (they're System-Manager-only per #48's schema) --
	but their run's own outcome must still be recorded, including a
	denial. Without this, a low-privileged identity's run would fail to
	even record its own Failed status, masking the real authorization
	denial behind an unrelated PermissionError on the bookkeeping write
	itself (confirmed empirically while testing issue #50's real,
	non-privileged node-permission-denial scenarios).
	"""
	step = frappe.new_doc("Flow Run Step")
	step.flow_run = run.name
	step.step_index = step_index
	step.node_id = node["id"]
	step.node_type = node["type"]
	step.status = "Running"
	step.attempt = attempt
	step.started_at = frappe.utils.now_datetime()
	step.input_snapshot = json.dumps(context, sort_keys=True)
	step.insert(ignore_permissions=True)
	return step


def _finish_step(step, status: str, started_monotonic: float, output: dict | None, error: str | None) -> None:
	step.status = status
	step.finished_at = frappe.utils.now_datetime()
	step.duration_ms = int((time.monotonic() - started_monotonic) * 1000)
	if output is not None:
		step.output_snapshot = json.dumps(output, sort_keys=True)
	if error is not None:
		step.error = error
	step.save(ignore_permissions=True)  # bookkeeping write -- see _create_step's docstring
	_commit_unless_testing()


def _commit_unless_testing() -> None:
	"""Commit after every persisted step, per the design doc ("commit
	after every step, not only at run end") -- so a worker-process crash
	mid-run loses at most the in-flight step, not the whole run's history
	so far. Skipped under `bench run-tests`: an explicit commit there
	would defeat FrappeTestCase's per-test rollback (confirmed: an
	earlier version of this module committed from resume_flow_run/
	cancel_flow_run and left real test users/Flow Runs behind in the
	database)."""
	if not frappe.flags.in_test:
		frappe.db.commit()


def _transition_run(
	run,
	status: str,
	*,
	error: str | None = None,
	output: str | None = None,
	started_at=None,
	finished_at=None,
) -> None:
	run.status = status
	if error is not None:
		run.error = error
	if output is not None:
		run.output = output
	if started_at is not None:
		run.started_at = started_at
	if finished_at is not None:
		run.finished_at = finished_at
	run.save(ignore_permissions=True)  # bookkeeping write -- see _create_step's docstring
	_commit_unless_testing()


def _is_cancelled(run_name: str) -> bool:
	return frappe.db.get_value("Flow Run", run_name, "status") == "Cancelled"


def resume_flow_run(run_name: str) -> None:
	"""Resume a Waiting run (whitelisted in api.py). Atomically guards
	against replay: only one caller can ever flip Waiting -> Running for
	a given run (a second, concurrent resume call affects zero rows and
	is rejected)."""
	_authorize_run_control(run_name)
	_flip_run_waiting_to_running_or_throw(run_name)
	frappe.enqueue(execute_flow_run, queue="default", run_name=run_name)


def _flip_run_waiting_to_running_or_throw(run_name: str) -> None:
	frappe.db.sql(
		"UPDATE `tabFlow Run` SET `status`=%s, `modified`=%s WHERE `name`=%s AND `status`=%s",
		("Running", frappe.utils.now(), run_name, "Waiting"),
	)
	affected = frappe.db.sql("SELECT ROW_COUNT()")[0][0]
	# No explicit frappe.db.commit() here: the anti-replay guarantee comes
	# from InnoDB's row lock on the UPDATE ... WHERE status='Waiting' plus
	# the ROW_COUNT() check, not from committing early -- a concurrent
	# resume blocks on the same row and sees 0 rows affected once it can
	# proceed, regardless of when this transaction is committed. An
	# explicit commit here would also break FrappeTestCase's per-test
	# rollback (confirmed: it left committed test users/Flow Runs behind).
	if affected == 0:
		frappe.throw(frappe._("Flow Run {0} is not Waiting (already resumed or terminal).").format(run_name))


def _create_approval_token(step, waiting: "NodeWaiting") -> None:
	"""Generate issue #50's Human Approval token: cryptographically
	random (secrets.token_urlsafe, 256 bits), never stored in plaintext
	(only its sha256 hash is persisted), scoped to this exact step, with
	a defensible expiry. Notifies `waiting.approver` via Frappe's native
	Notification Log (no custom notification engine) with a resume link
	carrying the plaintext token -- the only place it ever exists outside
	this function's local variable and the notified user's inbox.
	"""
	token = secrets.token_urlsafe(32)
	token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
	expires_at = frappe.utils.add_to_date(frappe.utils.now_datetime(), hours=waiting.expires_in_hours)

	frappe.db.set_value(
		"Flow Run Step",
		step.name,
		{"approval_token_hash": token_hash, "approval_expires_at": expires_at},
	)

	from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

	resume_url = frappe.utils.get_url(
		f"/api/method/itsuperapp.agent_flow.api.resume_flow_run_with_token"
		f"?run_name={step.flow_run}&token={token}"
	)
	enqueue_create_notification(
		users=[waiting.approver],
		doc={
			"type": "Alert",
			"subject": waiting.subject,
			"document_type": "Flow Run",
			"document_name": step.flow_run,
			"email_content": frappe._("Approve by visiting: {0}").format(resume_url),
			"from_user": frappe.session.user,
		},
	)


def resume_flow_run_with_token(run_name: str, token: str) -> None:
	"""Resume a Human Approval Waiting run via its token (whitelisted in
	api.py, `allow_guest=False` -- an authenticated session is required,
	so this is never a public unauthenticated resume). Unlike
	`resume_flow_run`, possession of the correct, unexpired, unused token
	scoped to this run's current Waiting step is itself the authorization
	-- the caller need not be the execution identity or a System Manager,
	since a real external approver may be neither.
	"""
	if frappe.session.user == "Guest":
		frappe.throw(frappe._("Authentication required."), frappe.PermissionError)

	waiting_step_name = frappe.db.get_value(
		"Flow Run Step",
		{"flow_run": run_name, "status": "Waiting"},
		"name",
		order_by="creation desc",
	)
	if not waiting_step_name:
		frappe.throw(frappe._("Flow Run {0} is not Waiting.").format(run_name))

	_verify_and_consume_approval_token(waiting_step_name, token)
	_flip_run_waiting_to_running_or_throw(run_name)
	frappe.enqueue(execute_flow_run, queue="default", run_name=run_name)


def _verify_and_consume_approval_token(step_name: str, token: str) -> None:
	step = frappe.db.get_value(
		"Flow Run Step",
		step_name,
		["approval_token_hash", "approval_expires_at", "approval_used_at"],
		as_dict=True,
	)
	if not step or not step.approval_token_hash:
		frappe.throw(frappe._("No approval token is pending for this run."), frappe.PermissionError)
	if step.approval_used_at:
		frappe.throw(frappe._("This approval token has already been used."), frappe.PermissionError)
	if step.approval_expires_at and frappe.utils.now_datetime() > step.approval_expires_at:
		frappe.throw(frappe._("This approval token has expired."), frappe.PermissionError)

	submitted_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
	if not secrets.compare_digest(submitted_hash, step.approval_token_hash):
		frappe.throw(frappe._("Invalid approval token."), frappe.PermissionError)

	# Atomic single-use guard, mirroring the run-level anti-replay pattern:
	# only the caller whose UPDATE actually flips a NULL approval_used_at
	# wins; a concurrent second submission of the same token affects 0 rows.
	frappe.db.sql(
		"UPDATE `tabFlow Run Step` SET `approval_used_at`=%s WHERE `name`=%s AND `approval_used_at` IS NULL",
		(frappe.utils.now(), step_name),
	)
	if frappe.db.sql("SELECT ROW_COUNT()")[0][0] == 0:
		frappe.throw(frappe._("This approval token has already been used."), frappe.PermissionError)


def cancel_flow_run(run_name: str) -> None:
	"""Cancel a Queued/Running/Waiting run (whitelisted in api.py).
	Idempotent: cancelling an already-terminal (including
	already-Cancelled) run is a silent no-op, never an error."""
	_authorize_run_control(run_name)
	current_status = frappe.db.get_value("Flow Run", run_name, "status")
	if current_status not in ("Queued", "Running", "Waiting"):
		return
	frappe.db.set_value("Flow Run", run_name, "status", "Cancelled", update_modified=True)


def _authorize_run_control(run_name: str) -> None:
	"""Only the run's own execution identity or a System Manager may
	resume/cancel it -- prevents an unrelated user from controlling
	someone else's run."""
	execution_identity = frappe.db.get_value("Flow Run", run_name, "execution_identity")
	if execution_identity is None:
		frappe.throw(frappe._("Flow Run {0} not found.").format(run_name))
	user = frappe.session.user
	if user == execution_identity:
		return
	if RESUMABLE_ROLES.intersection(frappe.get_roles(user)):
		return
	frappe.throw(
		frappe._("User {0} may not control Flow Run {1}.").format(user, run_name),
		frappe.PermissionError,
	)
