<script setup lang="ts">
/**
 * One video of the list (R-CH-10, design: Main.html). In milestone M2 a row
 * only shows: selecting, mirroring and the menu of a video arrive with
 * milestones M3 and M5.
 *
 * A thumbnail that is not cached yet is asked for again, once, each time
 * more pictures of the channel are cached (R-CH-16). Only a row whose
 * picture was missing follows that: the pictures of a large channel arrive
 * in hundreds of batches, and a batch must not redraw the whole list.
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { pictures } from '@/api/client'
import DateLabel from '@/components/DateLabel.vue'
import StatusChip from '@/components/StatusChip.vue'
import VideoRow from '@/components/VideoRow.vue'
import { useChannelsStore } from '@/stores/channels'

import type { VideoListRow } from './videoRows'

const props = defineProps<{
  /** The video and its texts. */
  row: VideoListRow
  /** The channel of the video. */
  channelId: string
}>()

const { t } = useI18n()
const channels = useChannelsStore()

/** How many batches of pictures of the channel are cached. It only grows. */
function picturesVersion(): number {
  return channels.byId.get(props.channelId)?.pictures ?? 0
}

/** The version of the pictures when the thumbnail was missing, or null when it never was. */
const missedAt = ref<number | null>(null)

const thumbnail = computed(() => {
  const id = props.row.video.id
  if (missedAt.value === null) {
    return pictures.thumbnail(id)
  }
  const version = picturesVersion()
  return version === missedAt.value ? pictures.thumbnail(id) : pictures.thumbnail(id, version)
})

function onPictureMissing(): void {
  missedAt.value ??= picturesVersion()
}
</script>

<template>
  <VideoRow
    :title="row.video.title"
    :thumbnail="thumbnail"
    :duration="row.duration"
    :new-tag="row.video.is_new ? t('channel.list.newTag') : undefined"
    :data-video="row.video.id"
    @picture-missing="onPictureMissing"
  >
    <template #facts>
      <DateLabel
        :text="row.date.text"
        :approximate="row.date.approximate"
        :note="t('channel.list.dateNote')"
      />
      <template v-if="row.views !== null">
        <span aria-hidden="true">{{ t('app.separator') }}</span>
        <span>{{ row.views }}</span>
      </template>
    </template>
    <template #status>
      <div class="flex flex-none flex-wrap justify-end gap-2">
        <StatusChip v-if="row.video.status === 'not_downloaded'">
          {{ t('channel.list.notDownloaded') }}
        </StatusChip>
        <StatusChip v-if="row.video.gone" tone="progress" icon="warning">
          {{ t('channel.list.removed') }}
        </StatusChip>
      </div>
    </template>
  </VideoRow>
</template>
