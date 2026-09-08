"""Post-install hooks for the itsuperapp Frappe app."""

from __future__ import annotations

import frappe


def after_install() -> None:
	"""Apply ITSUPERAPP/JasTel branding to Frappe Desk defaults.

	Frappe Desk's /login page still exists after the custom Frappe UI
	frontend (ADR 0006) takes over root "/" -- reachable if someone
	navigates to /login directly -- so it should carry the same JasTel
	branding rather than Frappe's default logo. This runs on every fresh
	`bench install-app itsuperapp` so the branding survives a rebuilt
	image/site instead of depending on a one-off `bench console` edit.
	"""
	set_jastel_branding()


def set_jastel_branding() -> None:
	website_settings = frappe.get_single("Website Settings")
	website_settings.app_name = "ITSUPERAPP"
	website_settings.app_logo = "/assets/itsuperapp/jastel-logo.svg"
	website_settings.save(ignore_permissions=True)
