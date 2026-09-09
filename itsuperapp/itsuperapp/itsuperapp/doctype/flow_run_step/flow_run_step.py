"""Flow Run Step DocType controller (issue #48).

One step within a Flow Run -- the audit/trace unit, per
docs/architecture/agent-flow-design.md -> "Persistence Model". A
standalone DocType with a Link back to Flow Run (not a Frappe child
table/`istable`): the design doc requires committing a step "after every
step, not only at run end," and a true Frappe child table only persists
when its *parent* document is saved, which would force re-saving the
whole Flow Run on every single step -- the wrong shape for high-frequency
incremental, independently-committed rows. This mirrors both Official
Flow's and FlowAgent's own Run/Step implementations (STEP 2 findings),
neither of which used a true child table for this either.

Each retry attempt gets its own Flow Run Step row (same `step_index`/
`node_id`, incrementing `attempt`) rather than one row mutated in place,
so the retry history itself is a queryable audit trail, not just the
final outcome.
"""

from __future__ import annotations

import frappe
from frappe.model.document import Document

# A step row is inserted already at its starting state (Running for an
# executed node, Skipped for a branch not taken -- there is no separate
# "Queued" phase per node within one synchronous graph-walk job).
VALID_TRANSITIONS: dict[str | None, set[str]] = {
	None: {"Running", "Skipped"},
	"Running": {"Success", "Failed", "Waiting", "Cancelled"},
	# Wave 2's minimal resume semantics: resuming a Waiting step means "the
	# wait condition is now satisfied", resolved directly to Success (no
	# real approval-payload/branching -- see runtime.py's NodeWaiting
	# docstring). Cancelled/Failed remain reachable from Waiting too.
	"Waiting": {"Running", "Success", "Cancelled", "Failed"},
	"Success": set(),
	"Failed": set(),
	"Skipped": set(),
	"Cancelled": set(),
}


class FlowRunStep(Document):
	def validate(self):
		self._validate_status_transition()

	def _validate_status_transition(self):
		previous_status = None if self.is_new() else frappe.db.get_value("Flow Run Step", self.name, "status")
		if previous_status == self.status:
			return
		allowed = VALID_TRANSITIONS.get(previous_status, set())
		if self.status not in allowed:
			frappe.throw(
				frappe._("Invalid Flow Run Step status transition: {0} -> {1}.").format(
					previous_status, self.status
				)
			)
