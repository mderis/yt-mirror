<script setup lang="ts">
/**
 * The first-run screen: shows the tools the app needs and downloads the
 * missing ones, one after another, with progress and a retry per failed step
 * (R-IN-03, design: Setup.html).
 *
 * It stays until the user presses "Continue", which is possible once every
 * tool is in order.
 */
import { onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import AppButton from '@/components/AppButton.vue'
import { BrandIcon } from '@/design/brand'
import { useToolsStore } from '@/stores/tools'

import ToolRow from './ToolRow.vue'

const { t } = useI18n()
const tools = useToolsStore()

onMounted(() => tools.installNextMissing())
// When one tool is done, or has failed, the next one starts.
watch(
  () => tools.installing,
  (busy) => {
    if (!busy) {
      void tools.installNextMissing()
    }
  },
)
</script>

<template>
  <main class="flex min-h-full justify-center bg-bg px-6 py-12 text-text">
    <div class="flex w-full max-w-170 flex-col gap-4">
      <div class="flex items-center gap-2 px-2">
        <BrandIcon class="size-6" />
        <span class="font-heading text-heading-sm font-semibold">{{ t('app.name') }}</span>
      </div>
      <h1 class="mt-3 font-heading text-heading-lg leading-heading font-semibold">
        {{ t('setup.title') }}
      </h1>
      <p class="text-text-muted">{{ t('setup.intro') }}</p>

      <ul class="flex flex-col gap-4">
        <ToolRow
          v-for="tool in tools.tools"
          :key="tool.name"
          :tool="tool"
          @retry="tools.install(tool.name)"
        />
      </ul>

      <div class="mt-2 flex flex-wrap items-center gap-3">
        <span class="flex-1 text-meta text-text-muted">{{ t('setup.size') }}</span>
        <AppButton variant="primary" :disabled="!tools.allReady" @press="tools.finishSetup()">
          {{ t('setup.continue') }}
        </AppButton>
      </div>
    </div>
  </main>
</template>
