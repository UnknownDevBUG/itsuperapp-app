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
	# `favicon` is a separate Website Settings field from `app_logo` --
	# unset, it falls back to Frappe's default, which on a site with
	# ERPNext installed resolves to ERPNext's own icon (the blue "E").
	# That fallback is what the browser shows enlarged as a loading
	# placeholder on slow-painting pages like /login, so it must be set
	# explicitly too or JasTel branding is inconsistent between the app
	# logo and the favicon/loading-placeholder icon.
	website_settings.favicon = "/assets/itsuperapp/logo.png"
	# `splash_image` is a THIRD, separate Website Settings field -- it
	# drives frappe/templates/includes/splash_screen.html, the full-page
	# logo shown for an instant right after a successful login (before
	# the redirect to /desk fires), rendered via
	# frappe/templates/includes/login/login.js. Left unset it falls back
	# to frappe/erpnext's own default logo, same failure mode as
	# `favicon` above -- distinct code path, so it needs its own field.
	# Uses the full animated wordmark (same asset as app_logo below), not
	# the icon-only logo.png used for favicon -- the splash is shown large
	# and full-page, so it should carry the full JasTel brand (globe +
	# "JasTel" text + tagline), not just the bare globe icon.
	website_settings.splash_image = "/assets/itsuperapp/jastel-logo.svg"
	website_settings.save(ignore_permissions=True)

	# Website Settings.app_logo (above) stopped controlling the login
	# page's logo as of frappe/frappe#27913 (fixing frappe/frappe#28402,
	# Nov 2024) -- Frappe now reads the login/navbar logo exclusively
	# from the separate "Navbar Settings" singleton doctype. Both must be
	# set or the login page keeps showing Frappe/ERPNext's default logo
	# even though Website Settings looks correctly configured.
	navbar_settings = frappe.get_single("Navbar Settings")
	navbar_settings.app_logo = "/assets/itsuperapp/jastel-logo.svg"
	navbar_settings.save(ignore_permissions=True)

	ensure_apps_screen_workspace()


def ensure_apps_screen_workspace() -> None:
	"""Create a minimal Workspace so ITSUPERAPP's tile shows on /apps.

	`add_to_apps_screen` in hooks.py registers ITSUPERAPP's app-switcher
	entry (icon/favicon/splash), but Frappe v16's Apps Page tiles are
	sourced from Workspace records linked to the app's Module Def, not
	from the hooks.py entry alone (confirmed via multiple
	discuss.frappe.io threads on "new app not showing on /apps" -- the
	consistent fix is "create a workspace and link the module"). With
	zero domain module UI yet (ADR 0006), this workspace is an
	intentionally empty placeholder just so the tile is clickable and
	routes somewhere sane; replace its content once a real module ships.
	"""
	if frappe.db.exists("Workspace", "ITSUPERAPP"):
		return

	module_name = frappe.db.exists("Module Def", {"app_name": "itsuperapp"})
	if not module_name:
		return

	workspace = frappe.new_doc("Workspace")
	workspace.label = "ITSUPERAPP"
	workspace.title = "ITSUPERAPP"
	workspace.module = module_name
	workspace.public = 1
	workspace.is_hidden = 0
	workspace.icon = "application"
	workspace.content = (
		'[{"id":"header","type":"header",'
		'"data":{"text":"<span class=\\"h4\\"><b>ITSUPERAPP</b></span>","col":12}}]'
	)
	workspace.insert(ignore_permissions=True)
