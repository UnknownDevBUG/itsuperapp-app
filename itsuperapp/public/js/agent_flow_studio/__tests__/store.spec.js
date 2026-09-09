import { describe, it, expect, beforeEach, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";

// `frappe` is a Desk-injected global at runtime (see agent_flow_studio.bundle.js
// and every other Agent Flow Studio module) -- stub it before importing the
// store, matching how frontend/src's own tests would need to for any
// Desk-context module.
globalThis.__ = (s) => s;
globalThis.frappe = {
	call: vi.fn(),
	db: { get_doc: vi.fn() },
	show_alert: vi.fn(),
};

const { useFlowStore } = await import("../store.js");

describe("useFlowStore", () => {
	beforeEach(() => {
		setActivePinia(createPinia());
		vi.clearAllMocks();
	});

	it("loads a flow definition and the node registry", async () => {
		globalThis.frappe.db.get_doc.mockResolvedValue({
			nodes: JSON.stringify([
				{ id: "n1", type: "noop", position: { x: 0, y: 0 }, config: {} },
			]),
			edges: JSON.stringify([]),
			viewport: JSON.stringify({ x: 1, y: 2, zoom: 1.5 }),
			settings: JSON.stringify({ max_steps: 10 }),
			schema_version: 1,
		});
		globalThis.frappe.call.mockResolvedValue({
			message: [{ type: "noop", label: "No-op", category: "Logic", config_schema: [] }],
		});

		const store = useFlowStore();
		await store.load("Test Flow");

		expect(store.flowDefinition).toBe("Test Flow");
		expect(store.graph.nodes).toHaveLength(1);
		expect(store.viewport).toEqual({ x: 1, y: 2, zoom: 1.5 });
		expect(store.settings).toEqual({ max_steps: 10 });
		expect(store.nodeRegistry).toHaveLength(1);
		expect(store.nodeRegistryByType.noop.label).toBe("No-op");
	});

	it("adds a node and selects it", () => {
		const store = useFlowStore();
		const id = store.addNode("noop", { x: 10, y: 20 });
		expect(store.graph.nodes).toHaveLength(1);
		expect(store.graph.nodes[0]).toMatchObject({
			id,
			type: "noop",
			position: { x: 10, y: 20 },
		});
		expect(store.selectedNodeId).toBe(id);
	});

	it("removing a node also removes edges touching it", () => {
		const store = useFlowStore();
		const a = store.addNode("noop", { x: 0, y: 0 });
		const b = store.addNode("noop", { x: 100, y: 0 });
		store.addEdge({ source: a, target: b });
		expect(store.graph.edges).toHaveLength(1);

		store.removeNode(a);
		expect(store.graph.nodes.map((n) => n.id)).toEqual([b]);
		expect(store.graph.edges).toHaveLength(0);
	});

	it("moveNode updates position without touching other nodes", () => {
		const store = useFlowStore();
		const a = store.addNode("noop", { x: 0, y: 0 });
		const b = store.addNode("noop", { x: 5, y: 5 });
		store.moveNode(a, { x: 50, y: 60 });
		expect(store.graph.nodes.find((n) => n.id === a).position).toEqual({ x: 50, y: 60 });
		expect(store.graph.nodes.find((n) => n.id === b).position).toEqual({ x: 5, y: 5 });
	});

	it("updateNodeConfig merges the new config onto the node", () => {
		const store = useFlowStore();
		const a = store.addNode("set_variable", { x: 0, y: 0 });
		store.updateNodeConfig(a, { variable_name: "x", value: 1 });
		expect(store.graph.nodes[0].config).toEqual({ variable_name: "x", value: 1 });
	});

	it("undo/redo restores prior graph states across add/remove", () => {
		const store = useFlowStore();
		const a = store.addNode("noop", { x: 0, y: 0 });
		expect(store.graph.nodes).toHaveLength(1);

		store.removeNode(a);
		expect(store.graph.nodes).toHaveLength(0);

		store.undo();
		expect(store.graph.nodes).toHaveLength(1);
		expect(store.graph.nodes[0].id).toBe(a);

		store.undo();
		expect(store.graph.nodes).toHaveLength(0);

		store.redo();
		expect(store.graph.nodes).toHaveLength(1);
	});

	it("removeEdge removes only the targeted edge", () => {
		const store = useFlowStore();
		const a = store.addNode("noop", { x: 0, y: 0 });
		const b = store.addNode("noop", { x: 100, y: 0 });
		const c = store.addNode("noop", { x: 200, y: 0 });
		store.addEdge({ source: a, target: b });
		store.addEdge({ source: b, target: c });
		const keepEdgeId = store.graph.edges[1].id;

		store.removeEdge(store.graph.edges[0].id);

		expect(store.graph.edges).toHaveLength(1);
		expect(store.graph.edges[0].id).toBe(keepEdgeId);
	});

	it("undo restores a node's prior position after a move", () => {
		const store = useFlowStore();
		const a = store.addNode("noop", { x: 0, y: 0 });
		store.moveNode(a, { x: 999, y: 999 });
		expect(store.graph.nodes[0].position).toEqual({ x: 999, y: 999 });

		store.undo();
		expect(store.graph.nodes[0].position).toEqual({ x: 0, y: 0 });
	});

	it("undo restores a removed edge", () => {
		const store = useFlowStore();
		const a = store.addNode("noop", { x: 0, y: 0 });
		const b = store.addNode("noop", { x: 100, y: 0 });
		store.addEdge({ source: a, target: b });
		expect(store.graph.edges).toHaveLength(1);

		store.removeEdge(store.graph.edges[0].id);
		expect(store.graph.edges).toHaveLength(0);

		store.undo();
		expect(store.graph.edges).toHaveLength(1);
		expect(store.graph.edges[0]).toMatchObject({ source: a, target: b });
	});

	it("vueFlowNodes derives label from the node registry, never a hardcoded map", () => {
		const store = useFlowStore();
		store.nodeRegistry = [{ type: "noop", label: "Totally Custom Label", category: "Logic" }];
		store.addNode("noop", { x: 1, y: 2 });
		expect(store.vueFlowNodes[0].label).toBe("Totally Custom Label");
	});

	it("vueFlowEdges maps source_port to VueFlow's sourceHandle", () => {
		const store = useFlowStore();
		const a = store.addNode("logic_condition", { x: 0, y: 0 });
		const b = store.addNode("noop", { x: 100, y: 0 });
		store.addEdge({ source: a, target: b, sourceHandle: "out-yes" });
		expect(store.vueFlowEdges[0]).toMatchObject({
			source: a,
			target: b,
			sourceHandle: "out-yes",
		});
	});

	it("save() calls frappe.client.set_value with the serialized graph, viewport, and settings; clears dirty on success", async () => {
		const store = useFlowStore();
		store.flowDefinition = "Test Flow";
		store.addNode("noop", { x: 0, y: 0 });
		store.viewport = { x: 5, y: 6, zoom: 2 };
		store.settings = { on_error: "Stop" };
		globalThis.frappe.call.mockResolvedValue({ message: {} });

		await store.save();

		expect(globalThis.frappe.call).toHaveBeenCalledWith(
			expect.objectContaining({
				method: "frappe.client.set_value",
				args: expect.objectContaining({
					doctype: "Flow Definition",
					name: "Test Flow",
					fieldname: expect.objectContaining({
						nodes: JSON.stringify(store.graph.nodes),
						edges: JSON.stringify(store.graph.edges),
						viewport: JSON.stringify({ x: 5, y: 6, zoom: 2 }),
						settings: JSON.stringify({ on_error: "Stop" }),
					}),
				}),
			})
		);
		expect(store.dirty).toBe(false);
	});

	it("save() surfaces a server validation error instead of silently succeeding", async () => {
		const store = useFlowStore();
		store.flowDefinition = "Test Flow";
		globalThis.frappe.call.mockRejectedValue(
			new Error("A Flow Definition must contain at least one node.")
		);

		await expect(store.save()).rejects.toThrow();
		expect(store.validationErrors).toEqual([
			"A Flow Definition must contain at least one node.",
		]);
	});
});
