<script setup lang="ts">
/**
 * One video of the list (R-CH-10, R-FB-02, design: Main.html and States.html).
 *
 * The row shows the status of the video as it is now: the list as loaded,
 * with the changes the events told since (R-FB-03). Its actions follow the
 * status (R-UI-09): Mirror a video that is not downloaded and still on YouTube
 * (R-MI-01, R-CH-14), Cancel
 * one that waits, downloads or is processed, up to the move of its file into
 * place (R-QU-02; Main.html shows no Cancel while processing), Retry a failed one
 * still on YouTube (R-QU-08, R-CH-14), Play
 * and Show in Finder a synced one (R-UI-10). The title opens the details
 * (R-UI-08). Its checkbox selects it, with Shift a range (R-MI-07); its menu
 * opens by a right-click and by "More actions" (R-UI-09). In the grid it is a
 * card (R-UI-03).
 *
 * A download that waits for room in the lookup budget says until when
 * (R-DT-06, D-090), one that failed in a way that passes when it is tried again
 * (R-QU-07). A synced file below the quality of its channel is marked
 * (R-QL-07); while it is downloaded again it stays synced and shows the
 * progress (R-QL-06, D-093).
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
import AppCheckbox from '@/components/AppCheckbox.vue'
import DateLabel from '@/components/DateLabel.vue'
import IconButton from '@/components/IconButton.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import StatusChip from '@/components/StatusChip.vue'
import VideoCard from '@/components/VideoCard.vue'
import VideoRow from '@/components/VideoRow.vue'
import { formatBytes, formatBytesOf, formatTime, roughTime } from '@/format'
import { clock } from '@/format/clock'
import { useChannelsStore } from '@/stores/channels'
import { useUiStore } from '@/stores/ui'
import { useVideosStore } from '@/stores/videos'
import { useViewStore } from '@/stores/view'

import VideoMenu from './VideoMenu.vue'
import { useDateOf, type VideoListRow } from './videoRows'

const props = withDefaults(
  defineProps<{
    /** The video and its texts, as the list was loaded. */
    row: VideoListRow
    /** The channel of the video. */
    channelId: string
    /** Whether it is drawn as a card of the grid (R-UI-03). */
    grid?: boolean
    /** The shown videos in their order, for a Shift-click range (R-MI-07). */
    shown?: readonly string[]
  }>(),
  { grid: false, shown: () => [] },
)

const { t, te } = useI18n()
const channels = useChannelsStore()
const videos = useVideosStore()
const ui = useUiStore()
const view = useViewStore()
const dateOf = useDateOf()

/** The menu of the video, while it is open: at the pointer, or under its button. */
const menu = ref<{ at?: { x: number; y: number } } | null>(null)
const selected = computed(() => view.selected.has(props.row.video.id))

/** The waiting download is paced by the lookup budget, until this time (D-090). */
const pacedText = computed(() =>
  video.value.paced_until
    ? t('channel.list.paced', { time: formatTime(video.value.paced_until, clock.timeZone) })
    : null,
)
/** A failure that passes is tried again at this time (R-QU-07). */
const retryText = computed(() =>
  video.value.retry_at && video.value.status === 'queued'
    ? t('channel.list.retryAt', { time: formatTime(video.value.retry_at, clock.timeZone) })
    : null,
)
/** A synced video that is downloaded again: it stays synced meanwhile (D-093). */
const redownloading = computed(
  () => video.value.status === 'synced' && Boolean(video.value.job_id) && !cancelling.value,
)

/** The video as it is now. */
const video = computed<Video>(() => videos.current(props.row.video))
const date = computed(() =>
  video.value === props.row.video ? props.row.date : dateOf(video.value),
)
const download = computed(() => videos.downloadOf(video.value.id))
/** The user cancelled the download and it is still ending (R-QU-02). */
const cancelling = computed(() => videos.isCancelling(props.row.video))
const isOpen = computed(() => videos.openVideoId === video.value.id)

/** The percent of the whole video that is done, or null when it is not known (R-QU-04). */
const percent = computed(() => {
  const fraction = download.value?.fraction
  return fraction === null || fraction === undefined ? null : Math.round(fraction * 100)
})

/** What the chip of a download says: the percent, else the bytes that arrived. */
const downloadingText = computed(() => {
  if (percent.value !== null) {
    return t('channel.list.downloading', { percent: percent.value })
  }
  const arrived = download.value?.downloaded_bytes
  return arrived
    ? t('channel.list.downloadingSize', { size: formatBytes(arrived) })
    : t('channel.list.downloadingStarting')
})

/**
 * "340 of 550 MB · about 2 min left" while bytes arrive, after the chip "Downloading 62%"
 * (R-QU-04, D-088). The time left appears once the measured speed is stable. A second
 * download of the video, without its subtitles, says so first.
 */
const progressFacts = computed(() => {
  const running = download.value
  const busy = video.value.status === 'downloading' || redownloading.value
  if (running === null || !busy || cancelling.value) {
    return null
  }
  const parts: string[] = []
  if (running.again) {
    parts.push(t('channel.list.again'))
  }
  const total = running.total_bytes ?? null
  const done = running.downloaded_bytes ?? null
  if (total !== null && done !== null) {
    parts.push(t('channel.list.bytesOf', formatBytesOf(done, total)))
  }
  if (running.left_s !== null) {
    const left = roughTime(running.left_s)
    parts.push(
      t('channel.list.aboutLeft', {
        time: t(`rough.${left.unit}`, { count: left.count }, left.count),
      }),
    )
  }
  return parts.length === 0 ? null : parts.join(` ${t('app.separator')} `)
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
    void ui.run(videos.cancel(jobId, video.value.id))
  }
}
</script>

<template>
  <component
    :is="grid ? VideoCard : VideoRow"
    :title="video.title"
    :thumbnail="thumbnail"
    :duration="row.duration"
    :new-tag="video.is_new ? t('channel.list.newTag') : undefined"
    :details-label="t('channel.list.details', { title: video.title })"
    :open="isOpen"
    :selected="selected"
    :data-video="video.id"
    :data-status="video.status"
    @picture-missing="onPictureMissing"
    @details="ui.run(videos.openDetails(video.id))"
    @menu="(at: { x: number; y: number }) => (menu = { at })"
  >
    <template #select>
      <AppCheckbox
        :model-value="selected"
        :label="t('channel.list.select', { title: video.title })"
        hide-label
        @pick="(on: boolean, shift: boolean) => view.pick(video.id, on, shift, shown)"
      />
    </template>
    <template #facts>
      <DateLabel
        :text="date.text"
        :approximate="date.approximate"
        :state="date.state"
        :note="date.note"
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
      <template v-if="pacedText">
        <span aria-hidden="true">{{ t('app.separator') }}</span>
        <span data-paced>{{ pacedText }}</span>
      </template>
      <template v-else-if="retryText">
        <span aria-hidden="true">{{ t('app.separator') }}</span>
        <span data-retry-at>{{ retryText }}</span>
      </template>
    </template>
    <template #progress>
      <ProgressBar
        v-if="
          (video.status === 'downloading' || video.status === 'processing' || redownloading) &&
          !cancelling &&
          (video.status !== 'synced' || download !== null)
        "
        class="mt-1 max-w-90"
        thin
        :value="video.status === 'processing' ? null : (download?.fraction ?? null)"
        :label="t('channel.list.progressLabel', { title: video.title })"
      />
    </template>
    <template #status>
      <div class="flex flex-none flex-wrap justify-end gap-2" data-chips>
        <StatusChip v-if="cancelling" tone="neutral" icon="retry">
          {{ t('channel.list.cancelling') }}
        </StatusChip>
        <StatusChip v-else-if="video.status === 'not_downloaded'">
          {{ t('channel.list.notDownloaded') }}
        </StatusChip>
        <StatusChip v-else-if="video.status === 'queued'" tone="neutral" icon="clock">
          {{ t('channel.list.queued') }}
        </StatusChip>
        <StatusChip v-else-if="video.status === 'downloading'" tone="progress" icon="download">
          {{ downloadingText }}
        </StatusChip>
        <StatusChip v-else-if="video.status === 'processing'" tone="progress" icon="retry">
          {{ t('channel.list.processing') }}
        </StatusChip>
        <StatusChip v-else-if="redownloading && download" tone="progress" icon="download">
          {{
            percent === null
              ? t('channel.list.redownloadingStarting')
              : t('channel.list.redownloading', { percent })
          }}
        </StatusChip>
        <StatusChip v-else-if="redownloading" tone="neutral" icon="clock">
          {{ t('channel.list.redownloadQueued') }}
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
        <StatusChip v-if="video.below_target" tone="neutral" icon="warning" data-below-target>
          {{ t('channel.list.belowTarget') }}
        </StatusChip>
      </div>
    </template>
    <template #actions>
      <div class="flex min-w-33 flex-none items-center justify-end gap-0.5" data-actions>
        <AppButton
          v-if="
            (video.status === 'not_downloaded' || video.status === 'file_missing') && !video.gone
          "
          icon="download"
          @press="ui.run(videos.mirror(video.id))"
        >
          {{
            video.status === 'file_missing'
              ? t('channel.list.mirrorAgain')
              : t('channel.list.mirror')
          }}
        </AppButton>
        <AppButton
          v-else-if="video.status === 'failed' && !video.gone"
          icon="retry"
          @press="ui.run(videos.retry(video.id))"
        >
          {{ t('channel.list.retryDownload') }}
        </AppButton>
        <AppButton
          v-else-if="
            (video.status === 'queued' ||
              video.status === 'downloading' ||
              video.status === 'processing' ||
              redownloading) &&
            video.job_id
          "
          variant="ghost"
          :busy="cancelling"
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
        <!-- A press on the button must not count as a click beside the menu, which closes it. -->
        <div class="relative" @mousedown.stop>
          <IconButton
            icon="more"
            :label="t('channel.list.moreActions', { title: video.title })"
            @press="menu = menu ? null : {}"
          />
          <VideoMenu v-if="menu" :video="video" :at="menu.at" @close="menu = null" />
        </div>
      </div>
    </template>
  </component>
</template>
