<template>
	<div class="afs-properties">
		<div v-if="!node" class="afs-properties-empty">
			{{ __("Select a node to edit its properties") }}
		</div>
		<template v-else>
			<div class="afs-properties-title">{{ node.type }}</div>
			<!--
				Issue #60 hard rule: this form is entirely driven by the
				selected node's config_schema from the Node Metadata API
				(passed in as `schema`) -- there is no hardcoded per-node-type
				form anywhere in this component. A node type with an empty
				config_schema (e.g. #61's noop) simply renders no fields.
			-->
			<div v-for="field in schema" :key="field.name" class="afs-field">
				<label>{{ field.label || field.name }}</label>
				<textarea
					v-if="field.type === 'JSON'"
					class="form-control"
					:value="jsonText(field.name)"
					@change="onJsonFieldChange(field.name, $event.target.value)"
				></textarea>
				<select
					v-else-if="field.type === 'Select'"
					class="form-control"
					:value="config[field.name]"
					@change="onFieldChange(field.name, $event.target.value)"
				>
					<option v-for="opt in selectOptions(field)" :key="opt" :value="opt">
						{{ opt }}
					</option>
				</select>
				<input
					v-else
					class="form-control"
					:type="field.type === 'Int' ? 'number' : 'text'"
					:value="config[field.name]"
					@change="onFieldChange(field.name, $event.target.value)"
				/>
			</div>
		</template>
	</div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	node: { type: Object, default: null },
	schema: { type: Array, default: () => [] },
});
const emit = defineEmits(["update"]);

const config = computed(() => (props.node && props.node.config) || {});

function selectOptions(field) {
	if (Array.isArray(field.options)) return field.options;
	if (typeof field.options === "string") return field.options.split("\n").filter(Boolean);
	return [];
}

function jsonText(fieldName) {
	const value = config.value[fieldName];
	return value === undefined ? "" : JSON.stringify(value, null, 2);
}

function onJsonFieldChange(fieldName, rawText) {
	let parsed;
	try {
		parsed = rawText.trim() === "" ? undefined : JSON.parse(rawText);
	} catch (e) {
		frappe.show_alert({ message: __("Invalid JSON for {0}", [fieldName]), indicator: "red" });
		return;
	}
	emit("update", { ...config.value, [fieldName]: parsed });
}

function onFieldChange(fieldName, value) {
	emit("update", { ...config.value, [fieldName]: value });
}
</script>

<style scoped>
.afs-properties {
	width: 280px;
	flex-shrink: 0;
	overflow-y: auto;
	border-left: 1px solid var(--border-color, #d1d8dd);
	padding: 10px;
}
.afs-properties-empty {
	color: var(--text-muted, #8d99a6);
	font-size: 12px;
}
.afs-properties-title {
	font-weight: 600;
	margin-bottom: 10px;
}
.afs-field {
	margin-bottom: 10px;
}
.afs-field label {
	display: block;
	font-size: 11px;
	color: var(--text-muted, #8d99a6);
	margin-bottom: 2px;
}
</style>
