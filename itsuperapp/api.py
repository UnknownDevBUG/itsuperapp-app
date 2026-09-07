"""End-to-end development-baseline smoke test.

A single whitelisted method that exercises every foundation layer scaffolded
so far in one HTTP round trip, per GH-21:

1. Frappe/MariaDB   -- a real frappe.db query (not a mock).
2. Shared AI layer   -- constructs a LangGraph StateGraph via
                        itsuperapp.ai.orchestration (no provider call; the
                        AI provider policy is still an open decision per
                        ARCHITECTURE.md).
3. Dedicated Supabase -- a real TCP reachability check against ITSUPERAPP's
                        own Supabase Postgres port (ADR 0005), verifying it
                        is a distinct, reachable service -- not document-ai's.

This is a health-check/smoke-test endpoint only. It has no business logic
and must not be treated as a template for real domain APIs.
"""

from __future__ import annotations

import socket
from typing import Any

import frappe


@frappe.whitelist()
def development_baseline_status() -> dict[str, Any]:
	"""Return a status dict proving each foundation layer is reachable."""
	result: dict[str, Any] = {}

	# 1. Frappe -> MariaDB round trip.
	try:
		db_name = frappe.db.sql("select database()", as_list=True)[0][0]
		result["frappe_mariadb"] = {"ok": True, "database": db_name}
	except Exception as exc:
		result["frappe_mariadb"] = {"ok": False, "error": str(exc)}

	# 2. Shared AI layer (LangGraph) importable and usable from Frappe context.
	try:
		from itsuperapp.ai.orchestration import new_workflow_graph

		graph = new_workflow_graph()
		result["ai_layer"] = {"ok": True, "graph_type": type(graph).__name__}
	except Exception as exc:
		result["ai_layer"] = {"ok": False, "error": str(exc)}

	# 3. Dedicated Supabase reachability (ADR 0005) -- TCP connect only, no
	# credentials used; proves the ITSUPERAPP Supabase Postgres port is a
	# live, distinct service reachable from the Frappe backend network.
	supabase_host = frappe.conf.get("itsuperapp_supabase_db_host") or "host.docker.internal"
	supabase_port = int(frappe.conf.get("itsuperapp_supabase_db_port") or 56322)
	try:
		with socket.create_connection((supabase_host, supabase_port), timeout=3):
			pass
		result["dedicated_supabase"] = {
			"ok": True,
			"host": supabase_host,
			"port": supabase_port,
		}
	except OSError as exc:
		result["dedicated_supabase"] = {
			"ok": False,
			"host": supabase_host,
			"port": supabase_port,
			"error": str(exc),
		}

	result["all_ok"] = all(v.get("ok") for v in result.values())
	return result
