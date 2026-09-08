<!--
  Animated color-mode toggle icon. Renders a single SVG whose sun/moon/
  monitor artwork is all real markup (not an emoji, not a static icon
  swap) and cross-fades + rotates between the three states with CSS
  transitions keyed off the `mode` prop.
-->
<script setup lang="ts">
import { computed } from 'vue'
import type { ColorModePreference } from '@/composables/useColorMode'

const props = defineProps<{
	mode: ColorModePreference
}>()

const isSun = computed(() => props.mode === 'light')
const isMoon = computed(() => props.mode === 'dark')
const isMonitor = computed(() => props.mode === 'system')
</script>

<template>
	<svg
		class="color-mode-icon"
		:class="mode"
		width="18"
		height="18"
		viewBox="0 0 24 24"
		fill="none"
		xmlns="http://www.w3.org/2000/svg"
		role="img"
		aria-hidden="true"
	>
		<!-- Sun: core disc + 8 rays. Rays scale/fade in and the whole glyph
		     rotates slowly while active. -->
		<g class="sun-glyph" :class="{ 'is-active': isSun }">
			<circle cx="12" cy="12" r="4.2" fill="currentColor" />
			<g class="sun-rays" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
				<line x1="12" y1="1.5" x2="12" y2="4" />
				<line x1="12" y1="20" x2="12" y2="22.5" />
				<line x1="1.5" y1="12" x2="4" y2="12" />
				<line x1="20" y1="12" x2="22.5" y2="12" />
				<line x1="4.4" y1="4.4" x2="6.1" y2="6.1" />
				<line x1="17.9" y1="17.9" x2="19.6" y2="19.6" />
				<line x1="4.4" y1="19.6" x2="6.1" y2="17.9" />
				<line x1="17.9" y1="6.1" x2="19.6" y2="4.4" />
			</g>
		</g>

		<!-- Moon: crescent formed by a circle minus an offset circle (mask),
		     with a couple of small "craters" that fade in once active. -->
		<g class="moon-glyph" :class="{ 'is-active': isMoon }">
			<mask id="moon-mask">
				<rect x="0" y="0" width="24" height="24" fill="white" />
				<circle cx="14" cy="9" r="7" fill="black" />
			</mask>
			<circle cx="12" cy="12" r="8" fill="currentColor" mask="url(#moon-mask)" />
			<circle class="moon-crater" cx="9" cy="15" r="1" fill="currentColor" opacity="0.35" />
			<circle class="moon-crater" cx="7.5" cy="11.5" r="0.6" fill="currentColor" opacity="0.35" />
		</g>

		<!-- Monitor: screen + stand, drawn with real geometry (not an emoji). -->
		<g class="monitor-glyph" :class="{ 'is-active': isMonitor }">
			<rect
				x="3"
				y="4.5"
				width="18"
				height="12"
				rx="1.5"
				stroke="currentColor"
				stroke-width="1.6"
				fill="none"
			/>
			<line x1="9" y1="20" x2="15" y2="20" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
			<line x1="12" y1="16.5" x2="12" y2="20" stroke="currentColor" stroke-width="1.6" />
		</g>
	</svg>
</template>

<style scoped>
.color-mode-icon {
	position: relative;
	overflow: visible;
}

.sun-glyph,
.moon-glyph,
.monitor-glyph {
	opacity: 0;
	transform-origin: 12px 12px;
	transform: scale(0.6) rotate(-40deg);
	transition:
		opacity 220ms ease,
		transform 260ms ease;
}

.sun-glyph.is-active,
.moon-glyph.is-active,
.monitor-glyph.is-active {
	opacity: 1;
	transform: scale(1) rotate(0deg);
}

/* Sun rays gently rotate for as long as light mode stays active. */
.sun-glyph.is-active .sun-rays {
	animation: sunSpin 12s linear infinite;
	transform-origin: 12px 12px;
}

@keyframes sunSpin {
	from {
		transform: rotate(0deg);
	}
	to {
		transform: rotate(360deg);
	}
}

.moon-glyph .moon-crater {
	transition: opacity 260ms ease 120ms;
}
.moon-glyph:not(.is-active) .moon-crater {
	opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
	.sun-glyph.is-active .sun-rays {
		animation: none;
	}
	.sun-glyph,
	.moon-glyph,
	.monitor-glyph {
		transition: opacity 120ms ease;
	}
}
</style>
