import { describe, it, expect, vi } from "vitest";
import { mount } from "@vue/test-utils";
import AgentFlowPalette from "../components/AgentFlowPalette.vue";

describe("AgentFlowPalette", () => {
	it("renders groups and items purely from the registry prop -- no hardcoded node-type list", () => {
		// A deliberately fictitious category/type pair: if this component
		// hardcoded any real category or node-type name anywhere, an
		// invented one like this would not render correctly.
		const registry = [
			{
				type: "zzz_invented_node",
				label: "Invented Node",
				category: "Zzz Invented Category",
			},
			{ type: "noop", label: "No-op", category: "Logic" },
		];
		const wrapper = mount(AgentFlowPalette, { props: { registry } });

		expect(wrapper.text()).toContain("Zzz Invented Category");
		expect(wrapper.text()).toContain("Invented Node");
		expect(wrapper.text()).toContain("Logic");
		expect(wrapper.text()).toContain("No-op");
	});

	it("groups multiple node types under the same category together", () => {
		const registry = [
			{ type: "a", label: "A", category: "Data" },
			{ type: "b", label: "B", category: "Data" },
		];
		const wrapper = mount(AgentFlowPalette, { props: { registry } });
		const groupTitles = wrapper.findAll(".afs-palette-group-title").map((n) => n.text());
		expect(groupTitles).toEqual(["Data"]);
		expect(wrapper.findAll(".afs-palette-item")).toHaveLength(2);
	});

	it("falls back to 'Other' for a node type with no declared category", () => {
		const registry = [{ type: "mystery", label: "Mystery" }];
		const wrapper = mount(AgentFlowPalette, { props: { registry } });
		expect(wrapper.text()).toContain("Other");
	});

	it("sets the node type as drag payload on dragstart, so drop can add the right node", async () => {
		const registry = [{ type: "set_variable", label: "Set Variable", category: "Data" }];
		const wrapper = mount(AgentFlowPalette, { props: { registry } });
		const setData = vi.fn();
		await wrapper.find(".afs-palette-item").trigger("dragstart", {
			dataTransfer: { setData, effectAllowed: "" },
		});
		expect(setData).toHaveBeenCalledWith("application/agent-flow-node-type", "set_variable");
	});
});
