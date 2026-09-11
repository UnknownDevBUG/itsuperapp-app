/**
 * Agent Flow Trigger -- Frappe Desk Calendar view ("default" calendar).
 *
 * Registered into `frappe.views.calendar`, the registry Frappe's
 * CalendarView reads when rendering a doctype's default Calendar
 * (frappe/public/js/frappe/views/calendar/calendar.js reads
 * frappe.views.calendar[this.doctype] for the default view).
 *
 * Every Agent Flow Trigger appears at its croniter-computed
 * `next_run`; the Flow Definition name is the event title.
 *
 * Dragging/resizing is disabled on purpose: next_run is derived from
 * the trigger's own cron_format (recomputed on save and refreshed by
 * the schedule dispatcher), so a hand-moved event would snap back.
 */
frappe.provide("frappe.views.calendar");

frappe.views.calendar["Agent Flow Trigger"] = {
	field_map: {
		id: "name",
		start: "next_run",
		end: "next_run",
		title: "flow_definition",
	},
	options: {
		editable: false,
		selectable: false,
		eventDrop: function () {},
		eventResize: function () {},
	},
};
