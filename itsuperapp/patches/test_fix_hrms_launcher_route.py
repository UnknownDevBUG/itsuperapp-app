"""Unit tests for the HRMS launcher compatibility patch."""

from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from itsuperapp.patches.fix_hrms_launcher_route import (
	_HRMS_DESKTOP_ICON,
	_HRMS_ROUTE,
	_OBSOLETE_ROUTE,
	execute,
)


class TestFixHrmsLauncherRoute(FrappeTestCase):
	@patch("itsuperapp.patches.fix_hrms_launcher_route.frappe.clear_cache")
	@patch("itsuperapp.patches.fix_hrms_launcher_route.frappe.db.set_value")
	@patch("itsuperapp.patches.fix_hrms_launcher_route.frappe.db.get_value")
	def test_replaces_only_the_obsolete_upstream_route(self, get_value, set_value, clear_cache):
		get_value.return_value = _OBSOLETE_ROUTE

		execute()

		get_value.assert_called_once_with(
			"Desktop Icon",
			{"name": _HRMS_DESKTOP_ICON, "app": "hrms"},
			"link",
		)
		set_value.assert_called_once_with(
			"Desktop Icon",
			_HRMS_DESKTOP_ICON,
			"link",
			_HRMS_ROUTE,
			update_modified=False,
		)
		clear_cache.assert_called_once_with()

	@patch("itsuperapp.patches.fix_hrms_launcher_route.frappe.clear_cache")
	@patch("itsuperapp.patches.fix_hrms_launcher_route.frappe.db.set_value")
	@patch("itsuperapp.patches.fix_hrms_launcher_route.frappe.db.get_value")
	def test_preserves_an_administrator_customized_route(self, get_value, set_value, clear_cache):
		get_value.return_value = "/app/hr-setup"

		execute()

		set_value.assert_not_called()
		clear_cache.assert_not_called()
