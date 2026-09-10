"""Agent Flow Trigger DocType controller (issue #62).

Canonical, single source of truth for DocType Event / Schedule / Webhook
trigger configuration -- Studio does not duplicate any of this (issue
#62's own "one source of truth" requirement); triggers are configured
here, as a plain Desk doctype, independently of the Flow graph itself.

Schedule triggers do not each get their own native `Scheduled Job Type`
record -- a single shared one (created once, idempotently, at migrate
time; see itsuperapp.agent_flow.triggers.ensure_schedule_dispatcher)
re-checks every enabled Schedule trigger's own `cron_format`/`last_run`
each minute. A per-trigger Scheduled Job Type was considered and
rejected: Frappe's scheduler invokes a Scheduled Job Type's `method` as
a bare zero-argument call with no reference back to which record fired
it (confirmed by reading scheduled_job_type.py's own `execute()`), so a
shared dispatcher that re-evaluates due-ness itself is simpler and
avoids needing to invent a correlation mechanism Frappe doesn't provide.
"""

from __future__ import annotations

import secrets

import frappe
from croniter import CroniterBadCronError, croniter
from frappe.model.document import Document

from itsuperapp.agent_flow.identity import is_valid_execution_identity


class AgentFlowTrigger(Document):
	def validate(self):
		self._validate_service_user()
		if self.trigger_type == "DocType Event":
			self._validate_doctype_event()
		elif self.trigger_type == "Schedule":
			self._validate_cron()
		elif self.trigger_type == "Webhook":
			self._validate_webhook_secret()
			self._ensure_webhook_key()

	def _validate_service_user(self):
		if not is_valid_execution_identity(self.service_user):
			frappe.throw(
				frappe._(
					"Service User {0} is not a valid execution identity -- it must be a real, "
					"enabled user, never Administrator or Guest."
				).format(self.service_user)
			)

	def _validate_doctype_event(self):
		if not frappe.db.exists("DocType", self.event_doctype):
			frappe.throw(frappe._("Unknown DocType: {0}").format(self.event_doctype))

	def _validate_cron(self):
		try:
			croniter(self.cron_format)
		except (CroniterBadCronError, ValueError):
			frappe.throw(frappe._("{0} is not a valid Cron expression.").format(self.cron_format))

	def _validate_webhook_secret(self):
		# Explicit check rather than relying solely on the field's
		# mandatory_depends_on (confirmed empirically: it did not block an
		# insert with no webhook_secret set for a Webhook-type trigger).
		if not self.webhook_secret:
			frappe.throw(frappe._("Webhook Secret is required for a Webhook trigger."))

	def _ensure_webhook_key(self):
		if not self.webhook_key:
			self.webhook_key = secrets.token_urlsafe(16)
