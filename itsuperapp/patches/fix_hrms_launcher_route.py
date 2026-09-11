"""Repair the obsolete Frappe HR Desktop launcher URL.

Frappe HR v16 currently ships a Desktop Icon pointing at ``/desk/people``.
That Desk page is not part of the app; its supported PWA entry point is
``/hrms``. Keep this compatibility repair in ITSUPERAPP rather than
modifying the upstream application.
"""

import frappe

_HRMS_DESKTOP_ICON = "Frappe HR"
_OBSOLETE_ROUTE = "/desk/people"
_HRMS_ROUTE = "/hrms"


def execute() -> None:
	"""Correct only the unchanged upstream default and preserve local choices."""
	current_route = frappe.db.get_value(
		"Desktop Icon",
		{"name": _HRMS_DESKTOP_ICON, "app": "hrms"},
		"link",
	)
	if current_route != _OBSOLETE_ROUTE:
		return

	frappe.db.set_value(
		"Desktop Icon",
		_HRMS_DESKTOP_ICON,
		"link",
		_HRMS_ROUTE,
		update_modified=False,
	)
	frappe.clear_cache()
