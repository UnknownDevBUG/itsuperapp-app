<template>
	<div class="agent-flow-studio">
		<div class="afs-toolbar">
			<button
				class="btn btn-xs btn-default"
				:disabled="!store.canUndo"
				@click="store.undo()"
			>
				{{ __("Undo") }}
			</button>
			<button
				class="btn btn-xs btn-default"
				:disabled="!store.canRedo"
				@click="store.redo()"
			>
				{{ __("Redo") }}
			</button>
			<button
				class="btn btn-xs btn-default"
				@click="deleteSelected"
				:disabled="!store.selectedNodeId"
			>
				{{ __("Delete") }}
			</button>
			<span v-if="store.validationErrors.length" class="afs-validation-error">
				{{ store.validationErrors[0] }}
			</span>
		</div>
		<div class="afs-body">
			<AgentFlowPalette :registry="store.nodeRegistry" />
			<div class="afs-canvas" @drop="onDrop" @dragover.prevent>
				<VueFlow
					:nodes="store.vueFlowNodes"
					:edges="store.vueFlowEdges"
					:default-viewport="store.viewport"
					@node-drag-stop="onNodeDragStop"
					@connect="onConnect"
					@node-click="onNodeClick"
					@pane-click="onPaneClick"
				>
					<Background />
					<Controls />
				</VueFlow>
			</div>
			<AgentFlowPropertiesPanel
				:node="store.selectedNode"
				:schema="selectedNodeSchema"
				@update="onConfigUpdate"
			/>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted } from "vue";
import { VueFlow, useVueFlow } from "@vue-flow/core";
import { Background } from "@vue-flow/background";
import { Controls } from "@vue-flow/controls";
import AgentFlowPalette from "./components/AgentFlowPalette.vue";
import AgentFlowPropertiesPanel from "./components/AgentFlowPropertiesPanel.vue";
import { useFlowStore } from "./store.js";
import "@vue-flow/core/dist/style.css";
import "@vue-flow/core/dist/theme-default.css";
import "@vue-flow/controls/dist/style.css";

const props = defineProps({ flowDefinition: { type: String, required: true } });

const store = useFlowStore();
const { project } = useVueFlow();

onMounted(() => {
	store.load(props.flowDefinition);
});

const selectedNodeSchema = computed(() => {
	if (!store.selectedNode) return [];
	const meta = store.nodeRegistryByType[store.selectedNode.type];
	return (meta && meta.config_schema) || [];
});

function onNodeDragStop({ node }) {
	store.moveNode(node.id, node.position);
}

function onConnect(connection) {
	store.addEdge(connection);
}

function onNodeClick({ node }) {
	store.selectNode(node.id);
}

function onPaneClick() {
	store.selectNode(null);
}

function onConfigUpdate(config) {
	if (store.selectedNodeId) store.updateNodeConfig(store.selectedNodeId, config);
}

function deleteSelected() {
	if (store.selectedNodeId) store.removeNode(store.selectedNodeId);
}

function onDrop(event) {
	const nodeType = event.dataTransfer.getData("application/agent-flow-node-type");
	if (!nodeType) return;
	const bounds = event.currentTarget.getBoundingClientRect();
	const position = project({ x: event.clientX - bounds.left, y: event.clientY - bounds.top });
	store.addNode(nodeType, position);
}
</script>

<style scoped>
.agent-flow-studio {
	display: flex;
	flex-direction: column;
	height: calc(100vh - 120px);
}
.afs-toolbar {
	display: flex;
	gap: 8px;
	align-items: center;
	padding: 6px 8px;
	border-bottom: 1px solid var(--border-color, #d1d8dd);
}
.afs-validation-error {
	color: var(--red-500, #e03636);
	font-size: 12px;
}
.afs-body {
	display: flex;
	flex: 1;
	min-height: 0;
}
.afs-canvas {
	flex: 1;
	min-width: 0;
	position: relative;
}
</style>
