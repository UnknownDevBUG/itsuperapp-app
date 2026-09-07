<script setup lang="ts">
import { createResource } from 'frappe-ui'

// Empty-shell placeholder page per ADR 0006's first round. Reuses the
// existing itsuperapp.api.development_baseline_status smoke-test endpoint
// (GH-21) just to prove the frontend can call the Frappe backend for real;
// this is not a real Home page for any domain module.
const ping = createResource({
	url: 'itsuperapp.api.development_baseline_status',
	auto: true,
})
</script>

<template>
	<div class="mx-auto max-w-3xl py-12">
		<h1 class="mb-4 text-lg font-semibold text-gray-900">ITSUPERAPP</h1>
		<p class="mb-6 text-sm text-gray-500">
			Frontend shell scaffold (ADR 0006). No domain module UI yet.
		</p>
		<pre class="rounded bg-gray-100 p-4 text-xs">{{ ping.data }}</pre>
	</div>
</template>
