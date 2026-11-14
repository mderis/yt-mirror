<script setup lang="ts">
/**
 * The progress of a full check (R-CH-27, docs/DESIGN.md section 8.3): how
 * many videos were read of about how many, and the button that cancels it.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { Progress } from '@/api/client'
import AppButton from '@/components/AppButton.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import { formatNumber } from '@/format'
import { useChannelsStore } from '@/stores/channels'
import { useUiStore } from '@/stores/ui'

const props = defineProps<{
  /** How far the full check has come. */
  progress: Progress
}>()

const { t } = useI18n()
const channels = useChannelsStore()
const ui = useUiStore()

const text = computed(() => {
  const done = formatNumber(props.progress.done)
  return props.progress.total === null
    ? t('channel.fullCheckProgressWithoutTotal', { done })
    : t('channel.fullCheckProgress', { done, total: formatNumber(props.progress.total) })
})

/** The share that is done. A channel can have grown, so it never exceeds the whole. */
const share = computed(() =>
  props.progress.total ? Math.min(props.progress.done / props.progress.total, 1) : null,
)
</script>

<template>
  <div class="flex flex-wrap items-center gap-3" data-full-check>
    <div class="min-w-0 flex-1">
      <p role="status">{{ text }}</p>
      <ProgressBar class="mt-2 max-w-105" :value="share" :label="t('channel.fullCheckLabel')" />
    </div>
    <AppButton
      variant="ghost"
      icon="stop"
      @press="ui.run(channels.cancelCheck(progress.channel_id))"
    >
      {{ t('channel.cancelCheck') }}
    </AppButton>
  </div>
</template>
