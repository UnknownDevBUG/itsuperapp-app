<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { call } from 'frappe-ui'
import { Button, FormControl, ErrorMessage } from 'frappe-ui'
import JastelLogo from '@/components/JastelLogo.vue'

const router = useRouter()

const form = reactive({
	usr: '',
	pwd: '',
})
const errorMessage = ref('')
const loading = ref(false)

async function handleLogin() {
	errorMessage.value = ''
	loading.value = true
	try {
		// Frappe's built-in login endpoint (frappe.auth) — session cookie based,
		// matching how Frappe Desk itself authenticates. No custom auth backend
		// yet; this is the Login page shell per ADR 0006's first-round scope.
		await call('login', { usr: form.usr, pwd: form.pwd })
		router.push({ name: 'Home' })
	} catch (error) {
		errorMessage.value =
			error instanceof Error ? error.message : 'Login failed. Please try again.'
	} finally {
		loading.value = false
	}
}
</script>

<template>
	<div class="flex min-h-screen items-center justify-center bg-gray-50">
		<div class="w-full max-w-sm rounded-lg border border-gray-200 bg-white p-8 shadow-sm">
			<div class="mb-8 flex justify-center">
				<JastelLogo :height="48" />
			</div>

			<form class="space-y-4" @submit.prevent="handleLogin">
				<FormControl
					v-model="form.usr"
					label="Email or Username"
					type="text"
					autocomplete="username"
					required
				/>
				<FormControl
					v-model="form.pwd"
					label="Password"
					type="password"
					autocomplete="current-password"
					required
				/>

				<ErrorMessage v-if="errorMessage" :message="errorMessage" />

				<Button variant="solid" :loading="loading" class="w-full" type="submit">
					Log in
				</Button>
			</form>
		</div>
	</div>
</template>
