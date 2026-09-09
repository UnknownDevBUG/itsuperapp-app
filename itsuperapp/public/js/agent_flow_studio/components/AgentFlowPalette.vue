<template>
	<div class="afs-palette">
		<div v-for="(items, category) in grouped" :key="category" class="afs-palette-group">
			<div class="afs-palette-group-title">{{ category }}</div>
			<div
				v-for="item in items"
				:key="item.type"
				class="afs-palette-item"
				draggable="true"
				@dragstart="onDragStart($event, item.type)"
			>
				{{ item.label || item.type }}
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";

// Hard rule (issue #60): palette contents come from the live Node
// Metadata API response only -- `registry` is a prop populated by the
// store's loadRegistry(), which calls itsuperapp.agent_flow.api.
// get_node_registry(). No hardcoded node-type list, no VALID_NODE_TYPES,
// no manual category list exists anywhere in this component or its
// parent -- grouping below is a pure `.category` reduce over whatever
// the API returned, so a new node type registered server-side (e.g. a
// future #51/#52 node) appears here with zero frontend changes.
const props = defineProps({ registry: { type: Array, required: true } });

const grouped = computed(() => {
	const out = {};
	for (const item of props.registry) {
		const category = item.category || "Other";
		(out[category] ||= []).push(item);
	}
	return out;
});

function onDragStart(event, nodeType) {
	event.dataTransfer.setData("application/agent-flow-node-type", nodeType);
	event.dataTransfer.effectAllowed = "move";
}
</script>

<style scoped>
.afs-palette {
	width: 220px;
	flex-shrink: 0;
	overflow-y: auto;
	border-right: 1px solid var(--border-color, #d1d8dd);
	padding: 8px;
}
.afs-palette-group-title {
	font-weight: 600;
	font-size: 11px;
	text-transform: uppercase;
	color: var(--text-muted, #8d99a6);
	margin: 10px 0 4px;
}
.afs-palette-item {
	padding: 6px 8px;
	margin-bottom: 4px;
	border: 1px solid var(--border-color, #d1d8dd);
	border-radius: 4px;
	cursor: grab;
	font-size: 12px;
	background: var(--fg-color, #fff);
}
</style>
