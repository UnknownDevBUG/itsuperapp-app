"""Agent Flow: canonical node registry and (future) execution runtime.

This package currently holds only the canonical node registry (issue #61):
a single Python source of truth for node-type metadata, consumed by
execution (#48), the core Frappe node set (#50), and Studio (#60) once
those land. No execution engine, DocTypes, or UI exist here yet -- see
docs/architecture/agent-flow-design.md and ADR 0012/0013 in the
UnknownDevBUG/itsuperapp infra repo for the full architecture.
"""

from __future__ import annotations
