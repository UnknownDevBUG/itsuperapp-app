import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { useManualRefHistory } from "@vueuse/core";

// Bounded history (issue #60's "don't snapshot every event" requirement):
// useManualRefHistory's own `capacity` option caps the undo stack, and we
// only ever call `history.commit()` after a *completed* structural change
// (add/remove node or edge, a finished node-drag, a properties-panel
// config change) -- never on every intermediate drag/mousemove frame.
const HISTORY_CAPACITY = 50;

export const useFlowStore = defineStore("agent-flow-studio-store", () => {
	const flowDefinition = ref(null);
	const graph = ref({ nodes: [], edges: [] });
	const viewport = ref({ x: 0, y: 0, zoom: 1 });
	const settings = ref({});
	const schemaVersion = ref(1);
	const nodeRegistry = ref([]);
	const selectedNodeId = ref(null);
	const validationErrors = ref([]);
	const dirty = ref(false);

	const history = useManualRefHistory(graph, {
		clone: true,
		capacity: HISTORY_CAPACITY,
	});

	const nodeRegistryByType = computed(() => {
		const map = {};
		for (const entry of nodeRegistry.value) map[entry.type] = entry;
		return map;
	});

	const selectedNode = computed(
		() => graph.value.nodes.find((n) => n.id === selectedNodeId.value) || null
	);

	// VueFlow-shaped view of our canonical domain graph (issue #60 §"Save/
	// load" -- Flow Definition's schema is the single source of truth;
	// this is a pure, derived rendering projection, never a second store).
	const vueFlowNodes = computed(() =>
		graph.value.nodes.map((n) => {
			const meta = nodeRegistryByType.value[n.type];
			return {
				id: n.id,
				type: "default",
				position: n.position || { x: 0, y: 0 },
				label: (meta && meta.label) || n.type,
				data: { nodeType: n.type, config: n.config || {} },
			};
		})
	);
	const vueFlowEdges = computed(() =>
		graph.value.edges.map((e) => ({
			id: e.id,
			source: e.source,
			target: e.target,
			sourceHandle: e.source_port || undefined,
		}))
	);

	async function loadRegistry() {
		const r = await frappe.call({ method: "itsuperapp.agent_flow.api.get_node_registry" });
		nodeRegistry.value = r.message || [];
	}

	async function load(name) {
		flowDefinition.value = name;
		const doc = await frappe.db.get_doc("Flow Definition", name);
		graph.value = {
			nodes: parseJsonField(doc.nodes) || [],
			edges: parseJsonField(doc.edges) || [],
		};
		viewport.value = parseJsonField(doc.viewport) || { x: 0, y: 0, zoom: 1 };
		settings.value = parseJsonField(doc.settings) || {};
		schemaVersion.value = doc.schema_version || 1;
		validationErrors.value = [];
		dirty.value = false;
		history.clear();
		await loadRegistry();
	}

	function parseJsonField(value) {
		if (value == null || value === "") return null;
		if (typeof value === "string") return JSON.parse(value);
		return value;
	}

	function commit() {
		history.commit();
		dirty.value = true;
	}

	function generateId() {
		return "n" + Math.random().toString(36).slice(2, 10);
	}

	function addNode(nodeType, position) {
		const id = generateId();
		graph.value = {
			...graph.value,
			nodes: [...graph.value.nodes, { id, type: nodeType, position, config: {} }],
		};
		commit();
		selectedNodeId.value = id;
		return id;
	}

	function removeNode(id) {
		graph.value = {
			nodes: graph.value.nodes.filter((n) => n.id !== id),
			edges: graph.value.edges.filter((e) => e.source !== id && e.target !== id),
		};
		if (selectedNodeId.value === id) selectedNodeId.value = null;
		commit();
	}

	function moveNode(id, position) {
		graph.value = {
			...graph.value,
			nodes: graph.value.nodes.map((n) => (n.id === id ? { ...n, position } : n)),
		};
		commit();
	}

	function updateNodeConfig(id, config) {
		graph.value = {
			...graph.value,
			nodes: graph.value.nodes.map((n) => (n.id === id ? { ...n, config } : n)),
		};
		commit();
	}

	function addEdge({ source, target, sourceHandle }) {
		const id = "e" + Math.random().toString(36).slice(2, 10);
		graph.value = {
			...graph.value,
			edges: [
				...graph.value.edges,
				{ id, source, target, source_port: sourceHandle || undefined },
			],
		};
		commit();
	}

	function removeEdge(id) {
		graph.value = { ...graph.value, edges: graph.value.edges.filter((e) => e.id !== id) };
		commit();
	}

	function selectNode(id) {
		selectedNodeId.value = id;
	}

	function undo() {
		history.undo();
	}

	function redo() {
		history.redo();
	}

	async function save() {
		validationErrors.value = [];
		try {
			await frappe.call({
				method: "frappe.client.set_value",
				args: {
					doctype: "Flow Definition",
					name: flowDefinition.value,
					fieldname: {
						nodes: JSON.stringify(graph.value.nodes),
						edges: JSON.stringify(graph.value.edges),
						viewport: JSON.stringify(viewport.value),
						settings: JSON.stringify(settings.value),
					},
				},
			});
			dirty.value = false;
			frappe.show_alert({ message: __("Flow saved"), indicator: "green" });
		} catch (e) {
			const message = (e && e.message) || __("Save failed");
			validationErrors.value = [message];
			frappe.show_alert({ message, indicator: "red" });
			throw e;
		}
	}

	return {
		flowDefinition,
		graph,
		viewport,
		settings,
		schemaVersion,
		nodeRegistry,
		nodeRegistryByType,
		selectedNodeId,
		selectedNode,
		validationErrors,
		dirty,
		vueFlowNodes,
		vueFlowEdges,
		load,
		loadRegistry,
		addNode,
		removeNode,
		moveNode,
		updateNodeConfig,
		addEdge,
		removeEdge,
		selectNode,
		undo,
		redo,
		save,
		canUndo: computed(() => history.canUndo.value),
		canRedo: computed(() => history.canRedo.value),
	};
});
