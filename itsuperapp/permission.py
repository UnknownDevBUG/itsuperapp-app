"""Frappe apps-screen permission check for ITSUPERAPP.

Referenced by hooks.py's `add_to_apps_screen` entry. Frappe's apps page
(and app-switcher/loading splash) calls this for every logged-in user to
decide whether ITSUPERAPP's tile/logo should appear at all. Any authenticated
user may see it -- there is no domain-specific role gate yet (no domain
module UI exists per ADR 0006's first round); tighten this once a real
permission model exists.
"""

from __future__ import annotations

import frappe


def has_app_permission() -> bool:
	"""Any logged-in (non-Guest) user can see the ITSUPERAPP tile."""
	return frappe.session.user != "Guest"
