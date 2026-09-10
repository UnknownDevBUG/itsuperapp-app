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
	"""Create/update the Workspace so ITSUPERAPP's tile shows on /apps and
	its real domain modules are reachable from /desk.

	`add_to_apps_screen` in hooks.py registers ITSUPERAPP's app-switcher
	entry (icon/favicon/splash), but Frappe v16's Apps Page tiles are
	sourced from Workspace records linked to the app's Module Def, not
	from the hooks.py entry alone (confirmed via multiple
	discuss.frappe.io threads on "new app not showing on /apps" -- the
	consistent fix is "create a workspace and link the module").

	Idempotent and re-run-safe (not just create-once): rebuilds
	`content`/`shortcuts` unconditionally even if the Workspace already
	exists, so a fresh `bench execute itsuperapp.install.ensure_apps_screen_workspace`
	on an already-installed site picks up newly added DocTypes (e.g.
	Document Extraction) without needing `bench reinstall`. A DocType
	shortcut here is what makes it reachable by clicking through /desk
	instead of typing /app/<doctype> directly -- Frappe does not add one
	automatically just because a DocType exists.
	"""
	module_name = frappe.db.exists("Module Def", {"app_name": "itsuperapp"})
	if not module_name:
		return

	shortcuts: list[dict[str, str]] = []
	if frappe.db.exists("DocType", "Document Extraction"):
		shortcuts.append({"label": "Document Extraction", "link_to": "Document Extraction"})

	content: list[dict] = [
		{
			"id": "header",
			"type": "header",
			"data": {"text": '<span class="h4"><b>ITSUPERAPP</b></span>', "col": 12},
		}
	]
	if shortcuts:
		content.append(
			{
				"id": "shortcuts-header",
				"type": "header",
				"data": {"text": '<span class="h4"><b>Shortcuts</b></span>', "col": 12},
			}
		)
		for shortcut in shortcuts:
			content.append(
				{
					"id": frappe.generate_hash(length=10),
					"type": "shortcut",
					"data": {"shortcut_name": shortcut["label"], "col": 3},
				}
			)

	if frappe.db.exists("Workspace", "ITSUPERAPP"):
		workspace = frappe.get_doc("Workspace", "ITSUPERAPP")
	else:
		workspace = frappe.new_doc("Workspace")
		workspace.label = "ITSUPERAPP"
		workspace.title = "ITSUPERAPP"
		workspace.module = module_name
		workspace.public = 1
		workspace.is_hidden = 0
		workspace.icon = "application"

	# `parent_page` must be an empty string, not the field's default None --
	# Frappe's sidebar builds a tree keyed on this field, and every other
	# working top-level Workspace (Home, Users, ...) has "" here. A None
	# (the state a workspace created before this fix landed can be stuck in)
	# leaves it out of the tree Frappe renders into the sidebar entirely --
	# it still exists and is directly reachable by URL, just invisible in
	# the nav. Set unconditionally (not just on create) so re-running this
	# on an already-installed site heals an existing bad value too.
	workspace.parent_page = workspace.parent_page or ""

	workspace.content = frappe.as_json(content)
	workspace.set("shortcuts", [])
	for shortcut in shortcuts:
		workspace.append(
			"shortcuts",
			{
				"type": "DocType",
				"link_to": shortcut["link_to"],
				"doc_view": "List",
				"label": shortcut["label"],
			},
		)
	workspace.save(ignore_permissions=True)
