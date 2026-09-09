import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount } from "@vue/test-utils";
import AgentFlowPropertiesPanel from "../components/AgentFlowPropertiesPanel.vue";

beforeEach(() => {
	globalThis.__ = (s) => s;
	globalThis.frappe = { show_alert: vi.fn() };
});

describe("AgentFlowPropertiesPanel", () => {
	it("shows a placeholder when no node is selected", () => {
		const wrapper = mount(AgentFlowPropertiesPanel, { props: { node: null, schema: [] } });
		expect(wrapper.text()).toContain("Select a node");
	});

	it("renders exactly the fields declared in config_schema -- no hardcoded per-node form", () => {
		const node = { type: "set_variable", config: { variable_name: "x", value: "1" } };
		const schema = [
			{ name: "variable_name", label: "Variable Name", type: "Data" },
			{ name: "value", label: "Value", type: "Data" },
		];
		const wrapper = mount(AgentFlowPropertiesPanel, { props: { node, schema } });
		const labels = wrapper.findAll(".afs-field label").map((n) => n.text());
		expect(labels).toEqual(["Variable Name", "Value"]);
	});

	it("emits an updated config object on a text field change", async () => {
		const node = { type: "set_variable", config: { variable_name: "x" } };
		const schema = [{ name: "variable_name", label: "Variable Name", type: "Data" }];
		const wrapper = mount(AgentFlowPropertiesPanel, { props: { node, schema } });

		await wrapper.find("input.form-control").setValue("renamed");
		const emitted = wrapper.emitted("update");
		expect(emitted[0][0]).toEqual({ variable_name: "renamed" });
	});

	it("renders a Select field's options and emits the chosen value", async () => {
		const node = { type: "logic_condition", config: { operator: "==" } };
		const schema = [
			{ name: "operator", label: "Operator", type: "Select", options: ["==", ">", "<"] },
		];
		const wrapper = mount(AgentFlowPropertiesPanel, { props: { node, schema } });

		const options = wrapper.findAll("option").map((o) => o.element.value);
		expect(options).toEqual(["==", ">", "<"]);

		await wrapper.find("select.form-control").setValue(">");
		expect(wrapper.emitted("update")[0][0]).toEqual({ operator: ">" });
	});

	it("parses a JSON field's textarea back into a real object on change", async () => {
		const node = { type: "frappe_create_document", config: { values: { a: 1 } } };
		const schema = [{ name: "values", label: "Field Values", type: "JSON" }];
		const wrapper = mount(AgentFlowPropertiesPanel, { props: { node, schema } });

		await wrapper.find("textarea.form-control").setValue('{"a": 2, "b": 3}');
		expect(wrapper.emitted("update")[0][0]).toEqual({ values: { a: 2, b: 3 } });
	});

	it("rejects invalid JSON without emitting a bad update", async () => {
		const node = { type: "frappe_create_document", config: { values: {} } };
		const schema = [{ name: "values", label: "Field Values", type: "JSON" }];
		const wrapper = mount(AgentFlowPropertiesPanel, { props: { node, schema } });

		await wrapper.find("textarea.form-control").setValue("{not valid json");
		expect(wrapper.emitted("update")).toBeUndefined();
		expect(globalThis.frappe.show_alert).toHaveBeenCalled();
	});
});
