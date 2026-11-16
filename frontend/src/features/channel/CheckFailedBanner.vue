<script setup lang="ts">
/**
 * The banner of a failed check (R-CH-25, design: StateError.html): what
 * happened and when, that the catalogue of the last successful check is
 * kept, and the button that checks again. While a new attempt waits or
 * runs, the banner stays, says so, and its button is busy (D-076).
 * "Show details" arrives with milestone M7.
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
/** A moment as the banner tells it: "11 Nov 2026, 21:40". */
function moment(seconds: number): string {
  return `${formatDate(seconds, clock.timeZone)}, ${formatTime(seconds, clock.timeZone)}`
}

const retrying = computed(() => props.channel.status === 'checking')
const failedAt = computed(() => {
  const at = props.channel.last_check_error_at
  return at === null ? null : t('channel.failed.failedAt', { when: moment(at) })
})

const kept = computed(() => {
  const last = props.channel.last_check_at
  if (last === null) {
    return t('channel.failed.noList')
  }
  return t('channel.failed.keptList', { when: moment(last) })
})
</script>

<template>
  <AppBanner tone="error" data-banner="check-failed">
    <p class="font-medium">{{ title }}</p>
    <p class="text-meta">
      <template v-if="retrying">{{ t('channel.failed.retrying') }} {{ kept }}</template>
      <template v-else>{{ failedAt }} {{ kept }} {{ texts.action }}</template>
    </p>
    <template #action>
      <AppButton
        icon="retry"
        :busy="channel.status === 'checking'"
        @press="ui.run(channels.check(channel.id, 'quick', 'retry'))"
      >
        {{ t('channel.failed.tryAgain') }}
      </AppButton>
    </template>
  </AppBanner>
</template>
