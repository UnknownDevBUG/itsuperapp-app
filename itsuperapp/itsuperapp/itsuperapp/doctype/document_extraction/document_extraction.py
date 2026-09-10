"""Document Extraction DocType controller.

Minimal document upload + AI-extracted-text record per Sprint 1 week's
Document AI scope (Roadmap Issue #28, Thursday 10 Sep): store the uploaded
file, its extraction status, and the raw text an AI provider returns. No
bounding-box UI or human review workflow yet -- that is explicitly deferred
to the next sprint per the roadmap's reduced scope note.
"""

from __future__ import annotations

from frappe.model.document import Document


class DocumentExtraction(Document):
	pass
