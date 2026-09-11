"""Add `next_run` to Agent Flow Trigger (Calendar view support).

Runs post_model_sync, so the `next_run` column already exists after
doctype sync. This patch only backfills `next_run` for existing
Schedule triggers from their own `cron_format` (croniter), so the
Frappe Desk Calendar shows every trigger without waiting for the next
scheduler tick. Idempotent: re-running just recomputes the same values.
"""

from datetime import datetime

import frappe
from croniter import CroniterBadCronError, croniter


def execute():
	if not frappe.db.has_column("Agent Flow Trigger", "next_run"):
		return

	triggers = frappe.get_all(
		"Agent Flow Trigger",
		filters={"trigger_type": "Schedule", "cron_format": ("is", "set")},
		fields=["name", "cron_format"],
	)
	for trigger in triggers:
		try:
			next_run = croniter(trigger.cron_format).get_next(datetime)
		except (CroniterBadCronError, ValueError):
			continue
		frappe.db.set_value("Agent Flow Trigger", trigger.name, "next_run", next_run)
