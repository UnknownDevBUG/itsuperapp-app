<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import JastelLogo from '@/components/JastelLogo.vue'
import ColorModeToggleIcon from '@/components/ColorModeToggleIcon.vue'
import { useColorMode } from '@/composables/useColorMode'

const route = useRoute()
const { preference, cyclePreference } = useColorMode()

// Empty-shell nav per ADR 0006's first round -- no domain module pages
// exist yet. Each module adds its own entry here as separate, later work.
const navItems = ref<{ label: string; to: string }[]>([{ label: 'Home', to: '/' }])

const colorModeLabel: Record<typeof preference.value, string> = {
	light: 'Light',
	dark: 'Dark',
	system: 'System',
}
</script>

<template>
	<!-- Login is a standalone full-screen page, not wrapped in the app shell. -->
	<router-view v-if="route.name === 'Login'" />

	<div v-else class="flex min-h-screen bg-gray-50 dark:bg-gray-900">
		<aside
			class="flex w-60 flex-shrink-0 flex-col border-r border-gray-200 bg-white dark:border-gray-800 dark:bg-black"
		>
			<div class="flex items-center border-b border-gray-100 px-4 py-4 dark:border-gray-800">
				<JastelLogo :height="32" clip-orbit />
			</div>
			<nav class="flex-1 space-y-1 p-2">
				<router-link
					v-for="item in navItems"
					:key="item.to"
					:to="item.to"
					class="block rounded px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
					active-class="bg-gray-100 font-medium text-gray-900 dark:bg-gray-800 dark:text-white"
				>
					{{ item.label }}
				</router-link>
			</nav>
		</aside>

		<div class="flex flex-1 flex-col">
			<header
				class="flex h-14 items-center justify-between border-b border-gray-200 bg-white px-6 dark:border-gray-800 dark:bg-black"
			>
				<span class="text-sm font-medium text-gray-600 dark:text-gray-300">ITSUPERAPP</span>
				<button
					type="button"
					class="flex items-center gap-2 rounded px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
					:title="`Color mode: ${colorModeLabel[preference]} (click to cycle)`"
					@click="cyclePreference"
				>
					<ColorModeToggleIcon :mode="preference" class="h-4 w-4 shrink-0" />
					<span>{{ colorModeLabel[preference] }}</span>
				</button>
			</header>
			<main class="flex-1 overflow-auto p-6">
				<router-view />
			</main>
		</div>
	</div>
</template>
