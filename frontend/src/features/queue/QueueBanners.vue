<script setup lang="ts">
/**
 * The banners of the queue (R-FB-04, design: States.html): the disk space guard
 * paused the queue, with "Resume anyway" (R-QU-10), and a channel folder that
 * cannot be reached holds its downloads, with "Try again" (R-QU-11). "Change
 * the limit" and "Choose folder" arrive with the settings screen of M7.
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import AppBanner from '@/components/AppBanner.vue'
import AppButton from '@/components/AppButton.vue'
import { formatBytes } from '@/format'
import { useChannelsStore } from '@/stores/channels'
import { useQueueStore } from '@/stores/queue'
import { useUiStore } from '@/stores/ui'

const { t } = useI18n()
const queue = useQueueStore()
const channels = useChannelsStore()
const ui = useUiStore()
/** The channel whose folder is looked at again, while it is. */
const trying = ref<string | null>(null)

const guard = computed(() => queue.summary.disk_guard ?? null)
const away = computed(() =>
  queue.summary.folders_away.map((id) => ({ id, title: channels.byId.get(id)?.title ?? id })),
)

async function tryAgain(channelId: string): Promise<void> {
  trying.value = channelId
  try {
    await queue.tryFolderAgain(channelId)
  } finally {
    trying.value = null
  }
}
</script>

<template>
  <AppBanner v-if="guard" tone="error" data-banner="disk-guard">
    {{
      t('queue.diskGuard', {
        free: formatBytes(guard.free_bytes),
        disk: guard.disk,
        limit: formatBytes(guard.limit_bytes),
      })
    }}
    <template #action>
      <AppButton @press="ui.run(queue.resumeAnyway())">{{ t('queue.resumeAnyway') }}</AppButton>
    </template>
  </AppBanner>
  <AppBanner v-for="channel in away" :key="channel.id" tone="error" data-banner="folder-away">
    {{ t('queue.folderAway', { channel: channel.title }) }}
    <template #action>
      <AppButton icon="retry" :busy="trying === channel.id" @press="ui.run(tryAgain(channel.id))">
        {{ t('queue.tryAgain') }}
      </AppButton>
    </template>
  </AppBanner>
</template>
