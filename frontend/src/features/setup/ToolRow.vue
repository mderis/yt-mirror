<script setup lang="ts">
/**
 * One tool of the first-run screen: its name, what it is for, and what is
 * happening to it right now (R-IN-03, design: Setup.html).
 *
 * Presentational: the page decides what a press on "Try again" does.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { Tool } from '@/api/client'
import AppButton from '@/components/AppButton.vue'
import AppIcon, { type IconName } from '@/components/AppIcon.vue'
import ProgressBar from '@/components/ProgressBar.vue'

const props = defineProps<{
  /** The tool and its state. */
  tool: Tool
}>()

defineEmits<{
  /** The user asked to try a failed installation again. */
  retry: []
}>()

const { t, te } = useI18n()

const failed = computed(() => props.tool.status === 'failed')
const waiting = computed(() => props.tool.status === 'missing' || props.tool.status === 'broken')
const icon = computed<IconName>(() => {
  if (props.tool.status === 'ok') return 'check'
  if (props.tool.status === 'installing') return 'download'
  return failed.value ? 'warning' : 'clock'
})
const iconColour = computed(() => {
  if (props.tool.status === 'ok') return 'text-ok-text'
  if (props.tool.status === 'installing') return 'text-warn-text'
  return failed.value ? 'text-err-text' : 'text-text-muted'
})
const percent = computed(() =>
  props.tool.progress === null ? null : Math.round(props.tool.progress * 100),
)
/** Why the installation failed, in the words written for its error code. */
const reason = computed(() => {
  const key = `setup.failure.${(props.tool.error_code ?? '').toLowerCase()}`
  return t(te(key) ? key : 'setup.failure.internal')
})
</script>

<template>
  <li
    class="flex flex-wrap items-center gap-3 rounded-lg border border-line bg-surface px-4 py-3"
    :data-tool="tool.name"
    :data-status="tool.status"
  >
    <span
      class="inline-flex size-9 flex-none items-center justify-center rounded-full bg-surface-raised"
      :class="iconColour"
    >
      <AppIcon :name="icon" />
    </span>
    <div class="min-w-0 flex-1 basis-64">
      <div class="font-semibold text-text">{{ t(`setup.tools.${tool.name}.name`) }}</div>
      <div class="text-meta text-text-muted">
        <template v-if="failed">{{ t('setup.failed', { reason }) }}</template>
        <template v-else-if="waiting && !tool.installable">{{ t('setup.cannotInstall') }}</template>
        <template v-else>{{ t(`setup.tools.${tool.name}.about`) }}</template>
      </div>
    </div>

    <div v-if="tool.status === 'installing'" class="flex-1 basis-48">
      <ProgressBar
        :value="tool.progress"
        :label="t('setup.progressLabel', { tool: t(`setup.tools.${tool.name}.name`) })"
      />
      <div class="mt-1 text-meta text-warn-text">
        {{ percent === null ? t('setup.downloadingUnknown') : t('setup.downloading', { percent }) }}
      </div>
    </div>
    <span v-else-if="tool.status === 'ok'" class="text-meta text-text-muted">
      {{ t('setup.installed') }}
    </span>
    <AppButton v-else-if="failed" icon="retry" @press="$emit('retry')">
      {{ t('setup.retry') }}
    </AppButton>
    <span v-else-if="tool.installable" class="text-text-muted">{{ t('setup.waiting') }}</span>
  </li>
</template>
