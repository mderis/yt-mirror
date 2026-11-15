<script setup lang="ts">
/**
 * One video of the list (R-CH-10, R-FB-02, design: Main.html and States.html).
 *
 * The row shows the status of the video as it is now: the list as loaded,
 * with the changes the events told since (R-FB-03). Its actions follow the
 * status (R-UI-09): Mirror a video that is not downloaded (R-MI-01), Cancel
 * one that waits, downloads or is processed, up to the move of its file into
 * place (R-QU-02; Main.html shows no Cancel while processing), Retry a failed one (R-QU-08), Play
 * and Show in Finder a synced one (R-UI-10). The title opens the details
 * (R-UI-08). Selecting several videos arrives with milestone M5.
 *
 * A thumbnail that is not cached yet is asked for again, once, each time
 * more pictures of the channel are cached (R-CH-16). Only a row whose
 * picture was missing follows that: the pictures of a large channel arrive
 * in hundreds of batches, and a batch must not redraw the whole list.
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { pictures, type Video } from '@/api/client'
import AppButton from '@/components/AppButton.vue'
import DateLabel from '@/components/DateLabel.vue'
import IconButton from '@/components/IconButton.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import StatusChip from '@/components/StatusChip.vue'
import VideoRow from '@/components/VideoRow.vue'
import { formatBytes, formatDuration } from '@/format'
import { useChannelsStore } from '@/stores/channels'
import { useUiStore } from '@/stores/ui'
import { useVideosStore } from '@/stores/videos'

import { useDateOf, type VideoListRow } from './videoRows'

const props = defineProps<{
  /** The video and its texts, as the list was loaded. */
  row: VideoListRow
  /** The channel of the video. */
  channelId: string
}>()

const { t, te } = useI18n()
const channels = useChannelsStore()
const videos = useVideosStore()
const ui = useUiStore()
const dateOf = useDateOf()

/** The video as it is now. */
const video = computed<Video>(() => videos.current(props.row.video))
const date = computed(() =>
  video.value === props.row.video ? props.row.date : dateOf(video.value),
)
const download = computed(() => videos.downloadOf(video.value.id))
const isOpen = computed(() => videos.openVideoId === video.value.id)

/** The percent of the stage that is done, or null when it is not known. */
const percent = computed(() => {
  const fraction = download.value?.fraction
  return fraction === null || fraction === undefined ? null : Math.round(fraction * 100)
})

/** "1080p · 3.1 MB/s · 1 min left" while bytes arrive (R-QU-04). */
const progressFacts = computed(() => {
  const running = download.value
  if (running === null || video.value.status !== 'downloading') {
    return null
  }
  const parts = [t(`channel.list.stage.${running.stage}`)]
  if (running.height !== null) {
    parts.push(t('channel.list.quality', { height: running.height }))
  }
  if (running.speed_bps !== null) {
    parts.push(t('channel.list.speed', { size: formatBytes(running.speed_bps) }))
  }
  if (running.left_s !== null) {
    parts.push(t('channel.list.left', { time: formatDuration(running.left_s) }))
  }
  return parts.join(` ${t('app.separator')} `)
})

/** The short reason of a failed download (R-QU-08). */
const reason = computed(() => {
  const code = video.value.error_code
  if (video.value.status !== 'failed' || code === null || code === undefined) {
    return null
  }
  const key = `channel.list.reason.${code.toLowerCase()}`
  return te(key) ? t(key) : t('channel.list.reason.internal')
})

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

function cancel(): void {
  const jobId = video.value.job_id
  if (jobId !== null && jobId !== undefined) {
    void ui.run(videos.cancel(jobId))
  }
}
</script>

<template>
  <VideoRow
    :title="video.title"
    :thumbnail="thumbnail"
    :duration="row.duration"
    :new-tag="video.is_new ? t('channel.list.newTag') : undefined"
    :details-label="t('channel.list.details', { title: video.title })"
    :open="isOpen"
    :data-video="video.id"
    :data-status="video.status"
    @picture-missing="onPictureMissing"
    @details="ui.run(videos.openDetails(video.id))"
  >
    <template #facts>
      <DateLabel
        :text="date.text"
        :approximate="date.approximate"
        :note="t('channel.list.dateNote')"
      />
      <template v-if="row.views !== null">
        <span aria-hidden="true">{{ t('app.separator') }}</span>
        <span>{{ row.views }}</span>
      </template>
      <template v-if="video.status === 'synced' && video.file_size">
        <span aria-hidden="true">{{ t('app.separator') }}</span>
        <span data-size>{{ formatBytes(video.file_size) }}</span>
      </template>
      <template v-if="progressFacts">
        <span aria-hidden="true">{{ t('app.separator') }}</span>
        <span class="text-warn-text" data-progress-facts>{{ progressFacts }}</span>
      </template>
      <template v-if="reason">
        <span aria-hidden="true">{{ t('app.separator') }}</span>
        <span class="text-err-text" data-reason>{{ reason }}</span>
      </template>
    </template>
    <template #progress>
      <ProgressBar
        v-if="video.status === 'downloading' || video.status === 'processing'"
        class="mt-1 max-w-90"
        thin
        :value="video.status === 'processing' ? null : (download?.fraction ?? null)"
        :label="t('channel.list.progressLabel', { title: video.title })"
      />
    </template>
    <template #status>
      <div class="flex flex-none flex-wrap justify-end gap-2" data-chips>
        <StatusChip v-if="video.status === 'not_downloaded'">
          {{ t('channel.list.notDownloaded') }}
        </StatusChip>
        <StatusChip v-else-if="video.status === 'queued'" tone="neutral" icon="clock">
          {{ t('channel.list.queued') }}
        </StatusChip>
        <StatusChip v-else-if="video.status === 'downloading'" tone="progress" icon="download">
          {{
            percent === null
              ? t('channel.list.downloadingStarting')
              : t('channel.list.downloading', { percent })
          }}
        </StatusChip>
        <StatusChip v-else-if="video.status === 'processing'" tone="progress" icon="retry">
          {{ t('channel.list.processing') }}
        </StatusChip>
        <StatusChip v-else-if="video.status === 'synced'" tone="ok" icon="check">
          {{
            video.height
              ? t('channel.list.synced', { height: video.height })
              : t('channel.list.syncedWithoutHeight')
          }}
        </StatusChip>
        <StatusChip v-else-if="video.status === 'file_missing'" tone="failed" icon="warning">
          {{ t('channel.list.fileMissing') }}
        </StatusChip>
        <StatusChip v-else-if="video.status === 'failed'" tone="failed" icon="warning">
          {{ t('channel.list.failedStatus') }}
        </StatusChip>
        <StatusChip v-if="video.gone" tone="progress" icon="warning">
          {{ t('channel.list.removed') }}
        </StatusChip>
      </div>
    </template>
    <template #actions>
      <div class="flex min-w-33 flex-none items-center justify-end gap-0.5" data-actions>
        <AppButton
          v-if="video.status === 'not_downloaded' || video.status === 'file_missing'"
          icon="download"
          @press="ui.run(videos.mirror(video.id))"
        >
          {{ t('channel.list.mirror') }}
        </AppButton>
        <AppButton
          v-else-if="video.status === 'failed'"
          icon="retry"
          @press="ui.run(videos.retry(video.id))"
        >
          {{ t('channel.list.retryDownload') }}
        </AppButton>
        <AppButton
          v-else-if="
            (video.status === 'queued' ||
              video.status === 'downloading' ||
              video.status === 'processing') &&
            video.job_id
          "
          variant="ghost"
          :aria-label="t('channel.list.cancelOf', { title: video.title })"
          @press="cancel"
        >
          {{ t('channel.list.cancel') }}
        </AppButton>
        <template v-else-if="video.status === 'synced'">
          <IconButton
            icon="play"
            :label="t('channel.list.play')"
            @press="ui.run(videos.play(video.id))"
          />
          <IconButton
            icon="reveal"
            :label="t('channel.list.reveal')"
            @press="ui.run(videos.reveal(video.id))"
          />
        </template>
      </div>
    </template>
  </VideoRow>
</template>
