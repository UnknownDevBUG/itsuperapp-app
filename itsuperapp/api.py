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


@frappe.whitelist()
def extract_document(file_url: str) -> dict[str, Any]:
	"""Create a Document Extraction record and run AI text extraction on it.

	Sprint 1 week scope (Roadmap Issue #28, Thursday 10 Sep): upload -> AI
	extraction of raw text only -- no bounding-box UI, no review workflow
	(both deferred to the next sprint per the roadmap's reduced scope note).

	`file_url` is an already-uploaded Frappe File's `file_url` (e.g. from
	`frappe.client.upload_file` or the frontend's file picker POSTing to
	`/api/method/upload_file` first) -- this endpoint does not itself accept
	multipart upload, it operates on a File that already exists, matching
	Frappe's standard two-step upload-then-process pattern.

	Synchronous by design for Sprint 1 week's scope (a single OpenRouter call
	per document, tested directly via bench console/curl per the roadmap's
	Thursday checklist) -- move to `frappe.enqueue` once multi-document/batch
	throughput matters.
	"""
	if not file_url:
		frappe.throw("file_url is required")

	file_doc = frappe.get_doc("File", {"file_url": file_url})
	file_bytes = file_doc.get_content()
	if isinstance(file_bytes, str):
		file_bytes = file_bytes.encode("utf-8")

	mime_type = file_doc.content_type or _guess_mime_type(file_doc.file_name or file_url)

	extraction = frappe.get_doc(
		{
			"doctype": "Document Extraction",
			"file": file_url,
			"status": "Processing",
		}
	)
	extraction.insert()
	# Commit here so the "Processing" row is visible to other requests/UI
	# polling immediately, even if the provider call below fails or is slow --
	# without this the row and its status flip would only become visible
	# together at the very end, defeating the point of a status field.
	frappe.db.commit()

	try:
		from itsuperapp.ai.model_registry import get_default_provider

		provider = get_default_provider()
		extracted_text = provider.invoke(
			"Extract all text content from this document, verbatim. "
			"Return only the extracted text, no commentary.",
			file_bytes=file_bytes,
			mime_type=mime_type,
		)
		extraction.status = "Done"
		extraction.extracted_text = extracted_text
	except Exception as exc:
		extraction.status = "Failed"
		extraction.error_message = str(exc)
	extraction.save()
	frappe.db.commit()

	return {
		"name": extraction.name,
		"status": extraction.status,
		"extracted_text": extraction.extracted_text,
		"error_message": extraction.error_message,
	}


def _guess_mime_type(filename: str) -> str:
	"""Best-effort MIME type from a filename when File.content_type is unset.

	Frappe's File doctype does not always populate `content_type` depending
	on the upload path taken, so this covers the document types Sprint 1
	week's demo actually needs (PDF, common images) rather than reaching for
	Python's full `mimetypes` module for a two-case lookup.
	"""
	lowered = filename.lower()
	if lowered.endswith(".pdf"):
		return "application/pdf"
	if lowered.endswith((".jpg", ".jpeg")):
		return "image/jpeg"
	if lowered.endswith(".png"):
		return "image/png"
	if lowered.endswith(".webp"):
		return "image/webp"
	raise ValueError(f"Unsupported file type for extraction: {filename}")
