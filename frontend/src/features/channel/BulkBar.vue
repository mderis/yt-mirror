<script setup lang="ts">
/**
 * The bar that appears while videos are selected (R-MI-07, design: Main.html):
 * how many, and what can be done with all of them at once: Mirror the ones
 * without a file (R-MI-01), Re-download the synced ones (R-QL-06), and Clear.
 * "Exclude forever" arrives with milestone M6.
 *
 * Mirror is an action of the user: its first 20 downloads are started by hand,
 * the others wait for room in the lookup budget (D-090).
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { Video } from '@/api/client'
import AppButton from '@/components/AppButton.vue'
import { formatNumber } from '@/format'
import { useUiStore } from '@/stores/ui'
import { useVideosStore } from '@/stores/videos'
import { useViewStore } from '@/stores/view'

const props = defineProps<{
  /** The selected videos, as they are now, in the order they are shown. */
  videos: readonly Video[]
}>()

const { t } = useI18n()
const view = useViewStore()
const catalogue = useVideosStore()
const ui = useUiStore()

const toMirror = computed(() =>
  props.videos
    .filter(
      (video) =>
        !video.gone && (video.status === 'not_downloaded' || video.status === 'file_missing'),
    )
    .map((video) => video.id),
)
const toRedownload = computed(() =>
  props.videos
    .filter((video) => !video.gone && video.status === 'synced' && !video.job_id)
    .map((video) => video.id),
)

async function mirror(): Promise<void> {
  await catalogue.mirrorMany(toMirror.value)
  view.clearSelection()
}

async function redownload(): Promise<void> {
  await catalogue.redownload(toRedownload.value)
  view.clearSelection()
}
</script>

<template>
  <div
    class="flex flex-wrap items-center gap-3 border-t border-line bg-surface-raised px-4 py-2"
    role="region"
    :aria-label="t('channel.bulk.label')"
    data-bulk-bar
  >
    <span class="font-medium" role="status">{{
      t('channel.bulk.selected', { count: formatNumber(videos.length) })
    }}</span>
    <AppButton icon="download" :disabled="toMirror.length === 0" @press="ui.run(mirror())">
      {{ t('channel.bulk.mirror') }}
    </AppButton>
    <AppButton icon="retry" :disabled="toRedownload.length === 0" @press="ui.run(redownload())">
      {{ t('channel.bulk.redownload') }}
    </AppButton>
    <AppButton variant="ghost" @press="view.clearSelection()">
      {{ t('channel.bulk.clear') }}
    </AppButton>
  </div>
</template>
