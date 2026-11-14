<script setup lang="ts">
/**
 * The banner of a failed check (R-CH-25, design: StateError.html): what
 * happened, that the catalogue of the last successful check is kept, and
 * the button that checks again. "Show details" arrives with milestone M7.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { Channel, ErrorCode } from '@/api/client'
import AppBanner from '@/components/AppBanner.vue'
import AppButton from '@/components/AppButton.vue'
import { formatDate, formatTime } from '@/format'
import { clock } from '@/format/clock'
import { useErrorTexts } from '@/i18n/errors'
import { useChannelsStore } from '@/stores/channels'
import { useUiStore } from '@/stores/ui'

const props = defineProps<{
  /** The channel whose last check failed. */
  channel: Channel
  /** The error code of that check. */
  code: ErrorCode
}>()

const { t } = useI18n()
const textsOf = useErrorTexts()
const channels = useChannelsStore()
const ui = useUiStore()

const texts = computed(() => textsOf(props.code))
const title = computed(() =>
  props.code === 'NETWORK_UNREACHABLE' ? t('channel.failed.reach') : texts.value.happened,
)
const kept = computed(() => {
  const last = props.channel.last_check_at
  if (last === null) {
    return t('channel.failed.noList')
  }
  const when = `${formatDate(last, clock.timeZone)}, ${formatTime(last, clock.timeZone)}`
  return t('channel.failed.keptList', { when })
})
</script>

<template>
  <AppBanner tone="error" data-banner="check-failed">
    <p class="font-medium">{{ title }}</p>
    <p class="text-meta">{{ kept }} {{ texts.action }}</p>
    <template #action>
      <AppButton
        icon="retry"
        :busy="channel.status === 'checking'"
        @press="ui.run(channels.check(channel.id, 'quick'))"
      >
        {{ t('channel.failed.tryAgain') }}
      </AppButton>
    </template>
  </AppBanner>
</template>
