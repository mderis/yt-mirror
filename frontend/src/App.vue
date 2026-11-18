<script setup lang="ts">
/**
 * The root of the interface.
 *
 * Until the window is connected it shows the connection page. Then the
 * first-run screen is shown as long as the tools need it (R-IN-03), and after
 * it the shell with the sidebar (R-UI-01). The question before a quit while
 * downloads run can come on either screen (R-QU-12).
 */
import { onMounted } from 'vue'

import ConnectionPage from '@/features/connection/ConnectionPage.vue'
import SetupPage from '@/features/setup/SetupPage.vue'
import AppShell from '@/features/shell/AppShell.vue'
import QuitConfirmDialog from '@/features/shell/QuitConfirmDialog.vue'
import { useAppStore } from '@/stores/app'
import { useToolsStore } from '@/stores/tools'
import { useUiStore } from '@/stores/ui'

const app = useAppStore()
const tools = useToolsStore()
const ui = useUiStore()

// The window connects once. The pages below only show what the stores know.
onMounted(() => app.connect())
</script>

<template>
  <ConnectionPage v-if="app.status !== 'ready'" />
  <SetupPage v-else-if="tools.inSetup" />
  <AppShell v-else />
  <QuitConfirmDialog v-if="app.status === 'ready' && ui.quitAsked" @close="ui.quitAsked = false" />
</template>
