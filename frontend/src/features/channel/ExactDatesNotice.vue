<script setup lang="ts">
/**
 * What the channel page says next to the progress of its exact dates
 * (R-DT-12, R-DT-15): a notice while a saved API key is not working ("Exact
 * dates: the API key is not working, using the slow way"), or the offer of
 * the key when the measured time left is over 10 minutes and no key is saved,
 * with that time. Each has a link that opens the key guide; nothing opens by
 * itself.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { Channel } from '@/api/client'
import AppBanner from '@/components/AppBanner.vue'
import AppButton from '@/components/AppButton.vue'
import { roughTime } from '@/format'
import { useUiStore } from '@/stores/ui'

const props = defineProps<{
  /** The channel whose exact dates are fetched. */
  channel: Channel
}>()

const { t } = useI18n()
const ui = useUiStore()

const left = computed(() => {
  const seconds = props.channel.exact_dates?.left_s ?? null
  if (seconds === null) {
    return null
  }
  const rough = roughTime(seconds)
  return t(`rough.${rough.unit}Left`, { count: rough.count }, rough.count)
})
const offer = computed(() => props.channel.exact_dates?.offer_key === true && left.value !== null)
</script>

<template>
  <AppBanner v-if="channel.key_notice" tone="attention" data-banner="key-notice">
    {{ t('apiKey.notice') }}
    <template #action>
      <AppButton icon="key" data-action="fix-key" @press="ui.openApiKey()">
        {{ t('apiKey.fix') }}
      </AppButton>
    </template>
  </AppBanner>
  <AppBanner v-else-if="offer" tone="info" data-banner="key-offer">
    {{ t('apiKey.offer', { left }) }}
    <template #action>
      <AppButton icon="key" data-action="offer-key" @press="ui.openApiKey()">
        {{ t('apiKey.offerAction') }}
      </AppButton>
    </template>
  </AppBanner>
</template>
