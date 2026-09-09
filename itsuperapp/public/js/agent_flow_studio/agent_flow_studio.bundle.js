import { createApp } from "vue";
import { createPinia } from "pinia";
import AgentFlowStudioComponent from "./AgentFlowStudio.vue";
import { useFlowStore } from "./store.js";

class AgentFlowStudio {
	constructor({ wrapper, page, flow_definition }) {
		this.$wrapper = $(wrapper);
		this.page = page;
		this.flow_definition = flow_definition;

		this.page.set_title(__("Agent Flow Studio: {0}", [this.flow_definition]));
		this.setup_page_actions();
		this.setup_app();
	}

	setup_page_actions() {
		this.page.clear_actions();
		this.page.clear_menu();
		this.page.clear_custom_actions();

		this.page.set_primary_action(__("Save"), () => this.store.save());
		this.page.add_button(__("Undo"), () => this.store.undo());
		this.page.add_button(__("Redo"), () => this.store.redo());
		this.page.add_menu_item(__("Go to Flow Definition"), () =>
			frappe.set_route("Form", "Flow Definition", this.flow_definition)
		);
	}

	setup_app() {
		let pinia = createPinia();
		let app = createApp(AgentFlowStudioComponent, { flowDefinition: this.flow_definition });
		app.use(pinia);
		this.$studio = app.mount(this.$wrapper.get(0));
		this.store = useFlowStore();
	}
}

frappe.provide("frappe.ui");
frappe.ui.AgentFlowStudio = AgentFlowStudio;
export default AgentFlowStudio;
