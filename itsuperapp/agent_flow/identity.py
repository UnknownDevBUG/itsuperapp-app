"""Execution identity resolution (issue #49).

ADR 0012 Security Model: "No Administrator by default, anywhere, ever --
the single most important constraint in this ADR." Execution identity
resolves in a fixed priority order and fails closed (returns None, never
raises a fallback default) if none of the candidates is valid:

    1. Triggering User  -- the user whose action (manual run, or a
       DocType-event save/submit) fired the trigger.
    2. Service User      -- an explicit, configured, least-privilege user
       set on the Trigger.
    3. Configured User   -- an explicit workflow-author choice.

"Administrator" is rejected as a resolved identity from every candidate
slot, not merely as a *default* -- Administrator has blanket Frappe
permissions (`frappe.has_permission` always returns True for it), so
routing execution through it would trivially satisfy 3 of the 4
permission-gate layers regardless of how it was chosen. That defeats the
purpose of the gate this module and `authorization.py` implement, so it
is never an acceptable execution identity, explicit or not. "Guest" is
rejected for the same reason from the opposite direction: it is not a
real, accountable actor.
"""

from __future__ import annotations

import frappe

DISALLOWED_IDENTITIES = frozenset({"Administrator", "Guest"})


class ExecutionIdentityError(Exception):
	"""Raised by callers that choose to treat unresolved identity as fatal.

	`resolve_execution_identity()` itself never raises this -- it returns
	`None` on failure (fail closed, per ADR 0012) so the caller can record
	an explicit FAILED Flow Run with a clear error, rather than an
	uncaught exception. This exception exists for callers that need to
	short-circuit immediately (e.g. before any Flow Run row exists yet).
	"""


def resolve_execution_identity(
	*,
	triggering_user: str | None = None,
	service_user: str | None = None,
	configured_user: str | None = None,
) -> str | None:
	"""Resolve the identity a Flow Run must execute as.

	Checks candidates in priority order (Triggering User, Service User,
	Configured User) and returns the first one that is a real, enabled,
	non-Administrator, non-Guest User. Returns `None` if none qualify --
	callers must treat `None` as fail-closed (the run does not start),
	never substitute a default.
	"""
	for candidate in (triggering_user, service_user, configured_user):
		if candidate and is_valid_execution_identity(candidate):
			return candidate
	return None


def is_valid_execution_identity(user: str) -> bool:
	"""True if `user` is a real, enabled User that may act as an execution
	identity -- i.e. not Administrator/Guest, and not disabled."""
	if user in DISALLOWED_IDENTITIES:
		return False
	return bool(frappe.db.get_value("User", {"name": user, "enabled": 1}))
