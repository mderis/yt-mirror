<script setup lang="ts">
/**
 * The banner of the "not a bot" check of YouTube (R-ER-05, R-FB-04): one
 * banner for the whole app, never one error per channel or video. It says
 * what the check is, that it depends on the network address, when the app
 * tries again and what the user can try. "Try now" ends the pause.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import AppBanner from '@/components/AppBanner.vue'
import AppButton from '@/components/AppButton.vue'
import { formatTime } from '@/format'
import { clock } from '@/format/clock'
import { useChannelsStore } from '@/stores/channels'
import { useUiStore } from '@/stores/ui'

const { t } = useI18n()
const channels = useChannelsStore()
const ui = useUiStore()

const trying = ref(false)

async function tryNow(): Promise<void> {
  trying.value = true
  await ui.run(channels.tryYouTubeNow())
  trying.value = false
}
</script>

<template>
  <AppBanner v-if="channels.youtubePause" data-banner="youtube-pause">
    <p class="font-medium">{{ t('youtubePause.title') }}</p>
    <p class="text-meta">
      {{
        t('youtubePause.text', { time: formatTime(channels.youtubePause.until, clock.timeZone) })
      }}
    </p>
    <template #action>
      <AppButton icon="retry" :busy="trying" @press="tryNow">
        {{ t('youtubePause.tryNow') }}
      </AppButton>
    </template>
  </AppBanner>
</template>
