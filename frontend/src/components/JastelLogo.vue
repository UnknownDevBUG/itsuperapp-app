<!--
  JasTel brand logo, ported from document-ai's React component
  (src/components/jastel-logo/index.tsx) to Vue 3 + TypeScript per ADR 0006.
  The animated SVG markup, brand color tokens, and behavior (light/dark mode,
  icon-only mode) are preserved; only the component framework changed.
-->
<script setup lang="ts">
import { computed, useId } from 'vue'
import { useColorMode } from '@/composables/useColorMode'
import { JASTEL_BRAND_COLORS } from '@/constants/brand'

const props = withDefaults(
	defineProps<{
		showText?: boolean
		height?: number
		/** Clips the orbiting-satellite animation to the icon's own box instead
		 * of letting it spill slightly outside (the source design's intent,
		 * safe in open layouts) — needed wherever something clickable sits
		 * close by, e.g. a sidebar's collapse trigger or menu, so the
		 * animation can't intercept clicks meant for it. */
		clipOrbit?: boolean
		/** Sub-wordmark tagline. document-ai's original component hardcoded
		 * "DOCUMENT AI" here; ITSUPERAPP is a different product built on the
		 * same JasTel brand, so this is a prop instead of a hardcoded string. */
		tagline?: string
	}>(),
	{
		showText: true,
		height: 56,
		clipOrbit: false,
		tagline: 'ITSUPERAPP',
	}
)

const uid = useId().replace(/:/g, '')
const { mode } = useColorMode()

// Icon-only mode crops to just the globe emblem's bounds instead of the full
// wordmark viewBox, so it doesn't render with a wide gap of empty space
// where the hidden text would have gone.
const viewBox = computed(() => (props.showText ? '-5 -5 235 80' : '-2 0 104 70'))
const tealColor = computed(() =>
	mode.value === 'dark'
		? JASTEL_BRAND_COLORS.WORDMARK_TEL_DARK
		: JASTEL_BRAND_COLORS.WORDMARK_TEL_LIGHT
)
const taglineColor = computed(() =>
	mode.value === 'dark' ? JASTEL_BRAND_COLORS.TAGLINE_DARK : JASTEL_BRAND_COLORS.TAGLINE_LIGHT
)
</script>

<template>
	<div class="flex items-center gap-3" :style="{ height: `${height}px` }">
		<svg
			:style="{
				height: `${height}px`,
				width: 'auto',
				overflow: clipOrbit ? 'hidden' : 'visible',
			}"
			:viewBox="viewBox"
			fill="none"
			xmlns="http://www.w3.org/2000/svg"
			role="img"
			aria-label="JasTel Logo"
		>
			<defs>
				<linearGradient :id="`jtGrad-${uid}`" x1="0%" y1="0%" x2="100%" y2="100%">
					<stop offset="0%" :stop-color="JASTEL_BRAND_COLORS.GLOBE_GRADIENT_START" />
					<stop offset="100%" :stop-color="JASTEL_BRAND_COLORS.GLOBE_GRADIENT_END" />
				</linearGradient>
				<clipPath :id="`jtClip-${uid}`">
					<circle cx="50" cy="35" r="30" />
				</clipPath>
			</defs>

			<g>
				<ellipse
					cx="50"
					cy="35"
					rx="40"
					ry="13"
					fill="none"
					:stroke="JASTEL_BRAND_COLORS.ORBIT_RING"
					stroke-width="0.8"
					stroke-dasharray="4 3"
					transform="rotate(-25 50 35)"
					opacity="0.5"
				/>

				<circle cx="50" cy="35" r="30" :fill="`url(#jtGrad-${uid})`" />

				<g :clip-path="`url(#jtClip-${uid})`">
					<path
						class="jt-land-anim"
						d="M25 25 Q 35 15, 45 30 T 70 20 Q 80 35, 60 50 T 30 40 Z M10 45 Q 15 50, 20 40 M85 30 Q 90 35, 80 40"
						:fill="JASTEL_BRAND_COLORS.LANDMASS_GREEN"
						fill-opacity="0.85"
					/>
				</g>

				<path
					d="M63 27 Q 71 31, 67 43"
					fill="none"
					:stroke="JASTEL_BRAND_COLORS.ATMOSPHERE_HIGHLIGHT"
					stroke-width="2"
					stroke-linecap="round"
					opacity="0.4"
				/>

				<g class="jt-ship-anim">
					<circle r="3.5" :fill="JASTEL_BRAND_COLORS.SATELLITE_ORANGE" />
					<circle r="1.5" :fill="JASTEL_BRAND_COLORS.SATELLITE_CORE" />
				</g>
			</g>

			<g v-if="showText">
				<text
					x="100"
					y="45"
					font-family="var(--font-kodchasan), sans-serif"
					font-weight="900"
					font-size="40"
					letter-spacing="-1.5"
				>
					<tspan :fill="JASTEL_BRAND_COLORS.SATELLITE_ORANGE">Jas</tspan>
					<tspan :fill="tealColor">Tel</tspan>
				</text>

				<text
					x="102"
					y="61"
					font-family="var(--font-kodchasan), sans-serif"
					font-weight="700"
					font-size="10"
					letter-spacing="2.2"
					:fill="taglineColor"
				>
					{{ tagline }}
				</text>
			</g>
		</svg>
	</div>
</template>

<style scoped>
@keyframes jtLandRotate {
	0% {
		transform: translateX(-24px);
	}
	50% {
		transform: translateX(24px);
	}
	100% {
		transform: translateX(-24px);
	}
}
/* Traces the same ellipse as the dashed orbit ring (cx=50 cy=35 rx=40
 * ry=13, rotated -25deg) instead of a plain circle, so the satellite
 * actually follows the drawn track instead of cutting across it.
 *
 * Real occlusion, not just dimming: the ellipse dips inside the globe's
 * r=30 disc only across parameter angle ~224.4deg-315.6deg (distance from
 * center under 30 there - solved from 169 + 1431*cos^2(t) = 30^2). That
 * stretch (62.333%-87.667% of the cycle below) is the only part of the
 * orbit actually behind the sphere, so the satellite is fully hidden
 * (opacity 0) there and fully visible everywhere else, instead of the
 * old opacity dip at 50% which — by this same math — is actually the
 * moment it's farthest OUTSIDE the globe's silhouette.
 */
@keyframes jtShipOrbit {
	0% {
		transform: translate(86.252px, 18.096px);
		opacity: 1;
	}
	8.333% {
		transform: translate(84.141px, 26.252px);
	}
	16.667% {
		transform: translate(72.884px, 36.751px);
	}
	25% {
		transform: translate(55.494px, 46.782px);
	}
	33.333% {
		transform: translate(36.632px, 53.655px);
	}
	41.667% {
		transform: translate(21.353px, 55.530px);
	}
	50% {
		transform: translate(13.748px, 51.904px);
	}
	58.333% {
		transform: translate(15.859px, 43.748px);
	}
	62.333% {
		transform: translate(20.247px, 38.839px);
		opacity: 1;
	}
	62.5% {
		transform: translate(20.247px, 38.839px);
		opacity: 0;
	}
	66.667% {
		transform: translate(27.116px, 33.249px);
		opacity: 0;
	}
	75% {
		transform: translate(44.506px, 23.218px);
		opacity: 0;
	}
	83.333% {
		transform: translate(63.368px, 16.345px);
		opacity: 0;
	}
	87.5% {
		transform: translate(72.069px, 14.677px);
		opacity: 0;
	}
	87.667% {
		transform: translate(72.069px, 14.677px);
		opacity: 1;
	}
	91.667% {
		transform: translate(78.647px, 14.470px);
	}
	100% {
		transform: translate(86.252px, 18.096px);
		opacity: 1;
	}
}
.jt-land-anim {
	animation: jtLandRotate 10s ease-in-out infinite;
}
.jt-ship-anim {
	animation: jtShipOrbit 8s linear infinite;
}
@media (prefers-reduced-motion: reduce) {
	.jt-land-anim,
	.jt-ship-anim {
		animation: none;
	}
}
</style>
