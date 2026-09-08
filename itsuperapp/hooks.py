app_name = "itsuperapp"
app_title = "ITSUPERAPP"
app_publisher = "UnknownDevBUG"
app_description = "ITSUPERAPP custom Frappe application: Core Platform and domain modules"
app_email = "noreply@itsuperapp.local"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "itsuperapp",
# 		"logo": "/assets/itsuperapp/logo.png",
# 		"title": "ITSUPERAPP",
# 		"route": "/itsuperapp",
# 		"has_permission": "itsuperapp.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/itsuperapp/css/itsuperapp.css"
# app_include_js = "/assets/itsuperapp/js/itsuperapp.js"

# include js, css files in header of web template
# web_include_css = "/assets/itsuperapp/css/itsuperapp.css"
# web_include_js = "/assets/itsuperapp/js/itsuperapp.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "itsuperapp/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "itsuperapp/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings). Route root "/" to
# ITSUPERAPP's custom Frappe UI frontend (Vue 3 SPA, ADR 0006) instead of
# Frappe's default /login + Desk, since Frappe resolves root "/" via
# get_home_page() (this hook) rather than website_route_rules -- the
# route rule below only applies once path != "index" (i.e. not root).
home_page = "frontend"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Website route rules
# --------------------
# Route ITSUPERAPP's custom Frappe UI frontend (Vue 3 SPA, see ADR 0006) at
# /frontend and all of its client-side sub-routes to the same built
# frontend.html shell, so Vue Router's history-mode navigation works on a
# full page load/refresh. Root "/" is handled separately via the home_page
# hook above (Frappe resolves root through get_home_page(), not this map).
website_route_rules = [
	{"from_route": "/frontend/<path:app_path>", "to_route": "frontend"},
]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "itsuperapp.utils.jinja_methods",
# 	"filters": "itsuperapp.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "itsuperapp.install.before_install"
# after_install = "itsuperapp.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "itsuperapp.uninstall.before_uninstall"
# after_uninstall = "itsuperapp.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "itsuperapp.utils.before_app_install"
# after_app_install = "itsuperapp.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "itsuperapp.utils.before_app_uninstall"
# after_app_uninstall = "itsuperapp.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "itsuperapp.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "itsuperapp.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["itsuperapp.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"itsuperapp.tasks.all"
# 	],
# 	"daily": [
# 		"itsuperapp.tasks.daily"
# 	],
# 	"hourly": [
# 		"itsuperapp.tasks.hourly"
# 	],
# 	"weekly": [
# 		"itsuperapp.tasks.weekly"
# 	],
# 	"monthly": [
# 		"itsuperapp.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "itsuperapp.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "itsuperapp.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "itsuperapp.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "itsuperapp.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["itsuperapp.utils.before_request"]
# after_request = ["itsuperapp.utils.after_request"]

# Job Events
# ----------
# before_job = ["itsuperapp.utils.before_job"]
# after_job = ["itsuperapp.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"itsuperapp.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
