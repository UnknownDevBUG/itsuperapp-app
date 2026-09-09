frappe.pages["agent-flow-studio"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Agent Flow Studio"),
		single_column: true,
	});

	if (frappe.boot.developer_mode) {
		frappe.hot_update = frappe.hot_update || [];
		frappe.hot_update.push(() => load_agent_flow_studio(wrapper));
	}
};

frappe.pages["agent-flow-studio"].on_page_show = function (wrapper) {
	load_agent_flow_studio(wrapper);
};

function load_agent_flow_studio(wrapper) {
	let route = frappe.get_route();
	let $parent = $(wrapper).find(".layout-main-section");
	$parent.empty();

	if (route.length > 1) {
		frappe.require("agent_flow_studio.bundle.js").then(() => {
			frappe.agent_flow_studio = new frappe.ui.AgentFlowStudio({
				wrapper: $parent,
				page: wrapper.page,
				flow_definition: route[1],
			});
		});
	} else {
		pick_or_create_flow(wrapper);
	}
}

function pick_or_create_flow(wrapper) {
	let d = new frappe.ui.Dialog({
		title: __("Open or Create an Agent Flow"),
		fields: [
			{
				label: __("Action"),
				fieldname: "action",
				fieldtype: "Select",
				options: [
					{ label: __("Create New"), value: "create" },
					{ label: __("Edit Existing"), value: "edit" },
				],
				default: "create",
				reqd: 1,
				onchange() {
					d.set_df_property("flow_name", "hidden", d.get_value("action") !== "edit");
					d.set_df_property(
						"new_flow_name",
						"hidden",
						d.get_value("action") !== "create"
					);
				},
			},
			{
				label: __("Flow"),
				fieldname: "flow_name",
				fieldtype: "Link",
				options: "Flow Definition",
				hidden: 1,
			},
			{
				label: __("Name"),
				fieldname: "new_flow_name",
				fieldtype: "Data",
			},
		],
		primary_action_label: __("Open"),
		primary_action(values) {
			if (values.action === "edit" && values.flow_name) {
				frappe.set_route("agent-flow-studio", values.flow_name);
			} else if (values.action === "create" && values.new_flow_name) {
				frappe.call({
					method: "itsuperapp.agent_flow.api.create_flow_definition",
					args: { flow_name: values.new_flow_name },
					callback(r) {
						if (r.message) {
							frappe.set_route("agent-flow-studio", r.message);
						}
					},
				});
			}
			d.hide();
		},
	});
	d.show();
}
