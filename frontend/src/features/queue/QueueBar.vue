<script setup lang="ts">
/**
 * The queue bar at the foot of a channel's page (design: Main.html): how many
 * downloads run and wait, about how long they still take and how fast, with
 * "Pause all" (R-QU-02) and "Show queue", which opens the downloads panel.
 * It is there while anything runs, waits, failed or is paused.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import AppButton from '@/components/AppButton.vue'
import { formatBytes, formatNumber, roughTime } from '@/format'
import { useQueueStore } from '@/stores/queue'
import { useUiStore } from '@/stores/ui'

const { t } = useI18n()
const queue = useQueueStore()
const ui = useUiStore()

const summary = computed(() => queue.summary)
const shown = computed(
  () =>
    summary.value.downloading > 0 ||
    summary.value.waiting > 0 ||
    summary.value.failed > 0 ||
    summary.value.paused,
)
const facts = computed(() => {
  const parts: string[] = []
  const { downloading, waiting, failed, paused } = summary.value
  if (paused) {
    parts.push(t('queue.paused'))
  }
  if (downloading > 0) {
    parts.push(t('queue.downloading', { count: formatNumber(downloading) }))
  }
  if (waiting > 0) {
    parts.push(t('queue.waiting', { count: formatNumber(waiting) }))
  }
  if (failed > 0) {
    parts.push(t('queue.failed', { count: formatNumber(failed) }))
  }
  if (queue.leftS !== null && downloading > 0) {
    const left = roughTime(queue.leftS)
    parts.push(
      t('queue.left', { time: t(`rough.${left.unit}`, { count: left.count }, left.count) }),
    )
  }
  if (queue.speed !== null && downloading > 0) {
    parts.push(t('queue.speed', { size: formatBytes(Math.round(queue.speed)) }))
  }
  return parts.join(` ${t('app.separator')} `)
})
</script>

<template>
  <div
    v-if="shown"
    class="flex flex-wrap items-center gap-3 border-t border-line bg-surface-side px-4 py-2"
    role="region"
    :aria-label="t('queue.bar')"
    data-queue-bar
  >
    <span class="font-medium">{{ t('queue.bar') }}</span>
    <span class="min-w-0 flex-1 text-text-muted" role="status">{{ facts }}</span>
    <AppButton
      variant="ghost"
      :icon="summary.paused ? 'resume' : 'pause'"
      @press="ui.run(summary.paused ? queue.resume() : queue.pause())"
    >
      {{ summary.paused ? t('queue.resumeAll') : t('queue.pauseAll') }}
    </AppButton>
    <AppButton @press="ui.run(queue.openPanel())">{{ t('queue.show') }}</AppButton>
  </div>
</template>
