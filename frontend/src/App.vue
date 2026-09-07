<script setup lang="ts">
import { ref } from "vue";
import { useRoute } from "vue-router";
import JastelLogo from "@/components/JastelLogo.vue";

const route = useRoute();

// Empty-shell nav per ADR 0006's first round -- no domain module pages
// exist yet. Each module adds its own entry here as separate, later work.
const navItems = ref<{ label: string; to: string }[]>([{ label: "Home", to: "/" }]);
</script>

<template>
  <!-- Login is a standalone full-screen page, not wrapped in the app shell. -->
  <router-view v-if="route.name === 'Login'" />

  <div v-else class="flex min-h-screen bg-gray-50">
    <aside class="flex w-60 flex-shrink-0 flex-col border-r border-gray-200 bg-white">
      <div class="flex items-center border-b border-gray-100 px-4 py-4">
        <JastelLogo :height="32" clip-orbit />
      </div>
      <nav class="flex-1 space-y-1 p-2">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="block rounded px-3 py-2 text-sm text-gray-700 hover:bg-gray-100"
          active-class="bg-gray-100 font-medium text-gray-900"
        >
          {{ item.label }}
        </router-link>
      </nav>
    </aside>

    <div class="flex flex-1 flex-col">
      <header class="flex h-14 items-center border-b border-gray-200 bg-white px-6">
        <span class="text-sm font-medium text-gray-600">ITSUPERAPP</span>
      </header>
      <main class="flex-1 overflow-auto p-6">
        <router-view />
      </main>
    </div>
  </div>
</template>
