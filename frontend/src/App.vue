<script setup lang="ts">
/**
 * The root of the interface.
 *
 * Until the window is connected it shows the connection page. Then the
 * first-run screen is shown as long as the tools need it (R-IN-03), and after
 * it the shell with the sidebar (R-UI-01).
 */
import { onMounted } from 'vue'

import ConnectionPage from '@/features/connection/ConnectionPage.vue'
import SetupPage from '@/features/setup/SetupPage.vue'
import AppShell from '@/features/shell/AppShell.vue'
import { useAppStore } from '@/stores/app'
import { useToolsStore } from '@/stores/tools'

const app = useAppStore()
const tools = useToolsStore()

// The window connects once. The pages below only show what the stores know.
onMounted(() => app.connect())
</script>

<template>
  <ConnectionPage v-if="app.status !== 'ready'" />
  <SetupPage v-else-if="tools.inSetup" />
  <AppShell v-else />
</template>
