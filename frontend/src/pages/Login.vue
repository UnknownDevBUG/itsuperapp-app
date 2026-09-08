<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { call } from 'frappe-ui'
import { Button, FormControl, ErrorMessage } from 'frappe-ui'
import JastelLogo from '@/components/JastelLogo.vue'
import { JASTEL_BRAND_COLORS } from '@/constants/brand'

const router = useRouter()

const form = reactive({
	usr: '',
	pwd: '',
})
const errorMessage = ref('')
const loading = ref(false)
const currentYear = new Date().getFullYear()

const brandAccentStyle = {
	background: `linear-gradient(90deg, ${JASTEL_BRAND_COLORS.SATELLITE_ORANGE}, ${JASTEL_BRAND_COLORS.WORDMARK_TEL_LIGHT}, ${JASTEL_BRAND_COLORS.GLOBE_GRADIENT_END})`,
}

const pageBackgroundStyle = {
	backgroundImage: `
		radial-gradient(circle at 20% 0%, ${JASTEL_BRAND_COLORS.SATELLITE_ORANGE}14, transparent 32rem),
		radial-gradient(circle at 80% 100%, ${JASTEL_BRAND_COLORS.GLOBE_GRADIENT_START}1f, transparent 34rem)
	`,
}

async function handleLogin() {
	errorMessage.value = ''
	loading.value = true
	try {
		// Frappe's built-in login endpoint (frappe.auth) — session cookie based,
		// matching how Frappe Desk itself authenticates. No custom auth backend
		// yet; this is the Login page shell per ADR 0006's first-round scope.
		await call('login', { usr: form.usr, pwd: form.pwd })
		router.push({ name: 'Home' })
	} catch {
		// ErrorMessage renders rich content internally, so never pass a raw
		// backend error into it. A stable message also avoids leaking account or
		// authentication details to unauthenticated users.
		errorMessage.value = 'Unable to sign in. Check your credentials and try again.'
	} finally {
		loading.value = false
	}
}
</script>

<template>
	<main
		class="relative isolate flex min-h-screen min-h-[100dvh] overflow-y-auto bg-gray-50 px-4 py-8 dark:bg-gray-900 sm:px-6"
		:style="pageBackgroundStyle"
	>
		<section class="relative mx-auto my-auto w-full max-w-md" aria-labelledby="login-title">
			<div
				class="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-xl shadow-gray-900/5 dark:border-gray-700 dark:bg-gray-800 dark:shadow-black/20"
			>
				<div class="h-1 w-full" :style="brandAccentStyle" aria-hidden="true" />

				<div class="px-7 py-8 sm:px-10 sm:py-10">
					<header class="mb-8 text-center">
						<div class="mb-6 flex justify-center">
							<JastelLogo :height="58" />
						</div>

						<h1
							id="login-title"
							class="text-2xl font-semibold tracking-tight text-gray-900 dark:text-white"
						>
							Sign in to ITSUPERAPP
						</h1>
						<p class="mt-2 text-sm leading-6 text-gray-500 dark:text-gray-300">
							Use your JasTel account to continue.
						</p>
					</header>

					<form class="space-y-5" :aria-busy="loading" @submit.prevent="handleLogin">
						<FormControl
							v-model="form.usr"
							label="Email or Username"
							name="usr"
							type="text"
							size="md"
							variant="outline"
							placeholder="yourname@jastel.co.th"
							autocomplete="username"
							autocapitalize="none"
							spellcheck="false"
							:disabled="loading"
							autofocus
							required
						/>
						<FormControl
							v-model="form.pwd"
							label="Password"
							name="pwd"
							type="password"
							size="md"
							variant="outline"
							placeholder="Enter your password"
							autocomplete="current-password"
							:disabled="loading"
							required
						/>

						<div aria-live="polite">
							<ErrorMessage v-if="errorMessage" :message="errorMessage" />
						</div>

						<Button
							theme="blue"
							variant="solid"
							size="lg"
							:loading="loading"
							loading-text="Signing in..."
							class="w-full"
							type="submit"
						>
							Log in
						</Button>
					</form>

					<footer
						class="mt-8 border-t border-gray-100 pt-5 text-center text-xs leading-5 text-gray-400 dark:border-gray-700 dark:text-gray-400"
					>
						<p>&copy; {{ currentYear }} JasTel Network Co., Ltd.</p>
						<p>All rights reserved.</p>
					</footer>
				</div>
			</div>
		</section>
	</main>
</template>
