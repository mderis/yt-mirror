<script setup lang="ts">
/**
 * The root of the interface. The sidebar shell of R-UI-01 arrives in milestone M2.
 *
 * Once the window is connected, the first-run screen is shown as long as the
 * tools need it (R-IN-03). Everything else is the placeholder page for now.
 */
import { onMounted } from 'vue'

import PlaceholderPage from '@/features/placeholder/PlaceholderPage.vue'
import SetupPage from '@/features/setup/SetupPage.vue'
import { useAppStore } from '@/stores/app'
import { useToolsStore } from '@/stores/tools'

const app = useAppStore()
const tools = useToolsStore()

// The window connects once. The pages below only show what the stores know.
onMounted(() => app.connect())
</script>

<template>
  <SetupPage v-if="app.status === 'ready' && tools.inSetup" />
  <PlaceholderPage v-else />
</template>
