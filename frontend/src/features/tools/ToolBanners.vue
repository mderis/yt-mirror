<script setup lang="ts">
/**
 * The banners for tools that are missing or broken after the first run
 * (R-IN-04): what is wrong, and the button that fixes it. While a tool is
 * being installed, its banner shows the progress instead.
 */
import { useI18n } from 'vue-i18n'

import type { Tool } from '@/api/client'
import AppBanner from '@/components/AppBanner.vue'
import AppButton from '@/components/AppButton.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import { useToolsStore } from '@/stores/tools'

const { t, te } = useI18n()
const tools = useToolsStore()

function nameOf(tool: Tool): string {
  return t(`setup.tools.${tool.name}.name`)
}

function reasonOf(tool: Tool): string {
  const key = `setup.failure.${(tool.error_code ?? '').toLowerCase()}`
  return t(te(key) ? key : 'setup.failure.internal')
}
</script>

<template>
  <div class="flex w-full flex-col gap-3">
    <template v-for="tool in tools.tools" :key="tool.name">
      <AppBanner v-if="tool.status === 'installing'" :data-banner="tool.name">
        <p>{{ t('toolBanner.installing', { tool: nameOf(tool) }) }}</p>
        <ProgressBar
          class="mt-2"
          :value="tool.progress"
          :label="t('setup.progressLabel', { tool: nameOf(tool) })"
        />
      </AppBanner>
      <AppBanner v-else-if="tool.status === 'failed'" tone="error" :data-banner="tool.name">
        {{ t('toolBanner.failed', { tool: nameOf(tool), reason: reasonOf(tool) }) }}
        <template #action>
          <AppButton icon="retry" @press="tools.install(tool.name)">
            {{ t('setup.retry') }}
          </AppButton>
        </template>
      </AppBanner>
      <AppBanner
        v-else-if="tool.status === 'missing' || tool.status === 'broken'"
        :data-banner="tool.name"
      >
        {{
          tool.installable
            ? t(`toolBanner.${tool.status}`, { tool: nameOf(tool) })
            : t('toolBanner.cannotInstall', { tool: nameOf(tool) })
        }}
        <template v-if="tool.installable" #action>
          <AppButton icon="download" @press="tools.install(tool.name)">
            {{ t('toolBanner.install') }}
          </AppButton>
        </template>
      </AppBanner>
    </template>
  </div>
</template>
