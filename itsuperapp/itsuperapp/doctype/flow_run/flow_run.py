"""Flow Run DocType controller (issue #48).

One execution of a Flow Version. Per docs/architecture/agent-flow-design.md
-> "Execution Model": status set Queued/Running/Waiting/Success/Failed/
Cancelled (Skipped is a Flow Run *Step* concept -- a branch not taken --
not meaningful for a whole run). `validate()` enforces the state machine
so no caller, including future code, can ever persist an impossible
transition (e.g. Success -> Running).
"""

from __future__ import annotations

import frappe
from frappe.model.document import Document

# None (a brand-new run) may only start life Queued. Terminal states
# (Success/Failed/Cancelled) accept no further transition at all.
VALID_TRANSITIONS: dict[str | None, set[str]] = {
	None: {"Queued"},
	"Queued": {"Running", "Failed", "Cancelled"},
	"Running": {"Waiting", "Success", "Failed", "Cancelled"},
	"Waiting": {"Running", "Cancelled", "Failed"},
	"Success": set(),
	"Failed": set(),
	"Cancelled": set(),
}


class FlowRun(Document):
	def validate(self):
		self._validate_status_transition()

	def _validate_status_transition(self):
		previous_status = None if self.is_new() else frappe.db.get_value("Flow Run", self.name, "status")
		if previous_status == self.status:
			return  # unchanged status, e.g. a re-save that only touches output -- always valid
		allowed = VALID_TRANSITIONS.get(previous_status, set())
		if self.status not in allowed:
			frappe.throw(
				frappe._("Invalid Flow Run status transition: {0} -> {1}.").format(
					previous_status, self.status
				)
			)
