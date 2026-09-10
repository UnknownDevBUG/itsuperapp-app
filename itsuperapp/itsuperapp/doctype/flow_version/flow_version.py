"""Flow Version DocType controller (issue #59).

An immutable, content-hash-deduped snapshot of a Flow Definition's graph
at save time, per docs/architecture/agent-flow-design.md -> "Persistence
Model". Execution (#48) always loads a Flow Version, never the live
mutable Flow Definition -- a deliberate, named fix for a FlowAgent bug
where editing a workflow mid-flight silently changed an already-paused
run's behavior (STEP 2 finding).

JSON field storage note: Frappe's "JSON" fieldtype only auto-serializes a
*dict* value to a JSON string on write, and never auto-deserializes on
read -- `doc.some_json_field` is whatever was last assigned, verbatim. A
Python *list* value is rejected outright at the DB-persistence boundary
(`Value for X cannot be a list`), regardless of fieldtype, for any
non-table field. Since `nodes`/`edges` are lists of objects (per the
design doc), every JSON-shaped field on Flow Definition/Flow Version is
stored and passed around as an explicit JSON **string** -- never a bare
Python list -- and parsed with `as_obj()` wherever the actual structure
(for validation, hashing, or a snapshot) is needed. This is a storage
mechanics detail, not a schema change: the field still logically holds
"JSON: node id, type, position, config" etc., exactly as the design doc
specifies.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import frappe
from frappe.model.document import Document


def as_obj(value: Any) -> Any:
	"""Parse a JSON-field value into its real Python structure.

	Accepts either an already-serialized JSON string (the normal case,
	since that's what's actually stored) or an already-parsed
	list/dict/None (defensive, in case a caller passes one directly) --
	either way, returns the real structure, never a raw string.
	"""
	if value in (None, ""):
		return None
	if isinstance(value, str):
		return json.loads(value)
	return value


def as_json(value: Any) -> str:
	"""Serialize a Python list/dict to the JSON string every JSON-shaped
	field on these DocTypes is actually stored as. Idempotent: passing an
	already-serialized string returns it unchanged (verified by
	round-tripping through `as_obj`, not just returned blindly, so a
	non-JSON string still fails loudly instead of being stored as-is).
	"""
	if isinstance(value, str):
		as_obj(value)  # raises json.JSONDecodeError if not actually valid JSON
		return value
	return json.dumps(value, sort_keys=True)


def compute_content_hash(
	nodes: Any,
	edges: Any,
	viewport: Any,
	settings: Any,
) -> str:
	"""Return a deterministic sha256 hash of the four snapshotted fields.

	Parses each value first (accepts either JSON strings or already-parsed
	structures) and re-serializes with `sort_keys=True`, so identical
	content always hashes the same way regardless of whether it arrived
	as a string or a structure, or what key order it was built in.
	Getting this right matters: FlowAgent's equivalent
	`_maybe_snapshot_version` had the right schema but a field-name bug in
	its actual implementation (STEP 2 finding) -- exactly the class of
	mistake a non-deterministic hash would silently reintroduce.
	"""
	canonical = json.dumps(
		{
			"nodes": as_obj(nodes),
			"edges": as_obj(edges),
			"viewport": as_obj(viewport),
			"settings": as_obj(settings),
		},
		sort_keys=True,
		default=str,
	)
	return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class FlowVersion(Document):
	def validate(self):
		if not self.is_new():
			frappe.throw(
				frappe._(
					"Flow Version records are immutable snapshots and cannot be "
					"modified after creation. Create a new Flow Version instead."
				)
			)
