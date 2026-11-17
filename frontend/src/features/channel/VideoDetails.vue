<script setup lang="ts">
/**
 * The details panel of a video (R-UI-08, R-UI-09, R-UI-10, design: Details.html).
 *
 * Beside the list: thumbnail, title, status, the actions of its status, the
 * facts of its file, its description and its chapters. Its actions in
 * milestone M3: Mirror, Play, Show in Finder and Open on YouTube. Copy link,
 * Re-download, Repair metadata and Exclude come with the milestones that
 * build their targets (D-066). Esc closes the panel.
 */
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'

import { pictures } from '@/api/client'
import AppButton from '@/components/AppButton.vue'
import DateLabel from '@/components/DateLabel.vue'
import IconButton from '@/components/IconButton.vue'
import StatusChip from '@/components/StatusChip.vue'
import { formatBytes, formatDate, formatDuration, formatTime } from '@/format'
import { clock } from '@/format/clock'
import { useUiStore } from '@/stores/ui'
import { useVideosStore } from '@/stores/videos'

import { useDateOf } from './videoRows'

const { t } = useI18n()
const videos = useVideosStore()
const ui = useUiStore()
const dateOf = useDateOf()

const details = computed(() => videos.details)
/** The video as it is now: the events may be newer than the details. */
const video = computed(() => {
  const loaded = details.value?.video
  return loaded ? videos.current(loaded) : null
})
const file = computed(() => details.value?.file ?? null)

function moment(seconds: number): string {
  return `${formatDate(seconds, clock.timeZone)}, ${formatTime(seconds, clock.timeZone)}`
}

const facts = computed(() => {
  const loaded = details.value
  const shown = video.value
  const current = file.value
  if (loaded === null || shown === null || current === null) {
    return []
  }
  const rows: { label: string; value: string; key: string }[] = [
    { key: 'name', label: t('details.name'), value: current.name },
    { key: 'folder', label: t('details.folder'), value: loaded.folder },
  ]
  if (current.size !== null) {
    rows.push({ key: 'size', label: t('details.size'), value: formatBytes(current.size) })
  }
  if (current.vcodec !== null) {
    rows.push({
      key: 'video',
      label: t('details.video'),
      value:
        current.width !== null && current.height !== null && current.fps !== null
          ? t('details.videoValue', {
              width: current.width,
              height: current.height,
              fps: Math.round(current.fps),
              codec: current.vcodec.toUpperCase(),
            })
          : t('details.videoWithoutSize', { codec: current.vcodec.toUpperCase() }),
    })
  }
  if (current.acodec !== null) {
    const channels =
      current.audio_channels === 2
        ? t('details.stereo')
        : current.audio_channels === 1
          ? t('details.mono')
          : t('details.channels', { count: current.audio_channels ?? 0 })
    rows.push({
      key: 'audio',
      label: t('details.audio'),
      value: t('details.audioValue', { codec: current.acodec, channels }),
    })
  }
  if (shown.published_at !== null) {
    rows.push({
      key: 'uploaded',
      label: t('details.uploaded'),
      value: t('details.uploadedValue', { date: moment(shown.published_at) }),
    })
  }
  if (loaded.downloaded_at !== null) {
    rows.push({
      key: 'downloaded',
      label: t('details.downloaded'),
      value: moment(loaded.downloaded_at),
    })
  }
  rows.push({
    key: 'thumbnail',
    label: t('details.thumbnail'),
    value: loaded.thumbnail_saved ? t('details.thumbnailBoth') : t('details.thumbnailEmbedded'),
  })
  rows.push({ key: 'video-id', label: t('details.videoId'), value: shown.id })
  return rows
})

function onKey(event: KeyboardEvent): void {
  if (event.key === 'Escape' && !event.defaultPrevented && ui.removeChannelId === null) {
    videos.closeDetails()
  }
}

onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <aside
    class="flex max-w-115 min-w-0 flex-1 basis-100 flex-col gap-4 overflow-y-auto border-l border-line bg-surface-side p-5"
    :aria-label="t('details.label')"
    data-details
  >
    <div class="flex items-center justify-between">
      <span class="text-label font-medium text-text-muted uppercase">
        {{ t('details.label') }}
      </span>
      <IconButton
        icon="close"
        size="sm"
        :label="t('details.close')"
        @press="videos.closeDetails()"
      />
    </div>
    <p v-if="details === null || video === null" class="text-text-muted" role="status">
      {{ t('details.loading') }}
    </p>
    <template v-else>
      <div class="relative aspect-video overflow-hidden rounded-lg bg-track">
        <img :src="pictures.thumbnail(video.id)" alt="" class="size-full object-cover" />
        <span
          v-if="video.duration_s !== null"
          class="absolute right-2 bottom-2 rounded-xs bg-scrim px-1 text-label text-on-scrim"
        >
          {{ formatDuration(video.duration_s) }}
        </span>
      </div>
      <h2 class="text-heading-md font-medium text-text" data-details-title>{{ video.title }}</h2>
      <div class="flex flex-wrap gap-2" data-details-chips>
        <StatusChip v-if="video.status === 'synced'" tone="ok" icon="check">
          {{
            video.height
              ? t('channel.list.synced', { height: video.height })
              : t('channel.list.syncedWithoutHeight')
          }}
        </StatusChip>
        <StatusChip v-else-if="video.status === 'failed'" tone="failed" icon="warning">
          {{ t('channel.list.failedStatus') }}
        </StatusChip>
        <StatusChip v-else-if="video.status === 'not_downloaded'">
          {{ t('channel.list.notDownloaded') }}
        </StatusChip>
        <StatusChip v-else tone="progress" icon="download">
          {{ t('channel.list.downloadingStarting') }}
        </StatusChip>
        <StatusChip v-if="file?.subtitles" icon="info">
          {{ file.subtitles === 'auto' ? t('details.autoSubtitles') : t('details.subtitles') }}
        </StatusChip>
        <StatusChip v-if="details.chapters.length > 0">
          {{ t('details.chapters', { count: details.chapters.length }, details.chapters.length) }}
        </StatusChip>
      </div>
      <div class="flex flex-wrap gap-2" data-details-actions>
        <template v-if="video.status === 'synced'">
          <AppButton variant="primary" icon="play" @press="ui.run(videos.play(video.id))">
            {{ t('details.play') }}
          </AppButton>
          <AppButton icon="reveal" @press="ui.run(videos.reveal(video.id))">
            {{ t('details.reveal') }}
          </AppButton>
        </template>
        <AppButton
          v-else-if="
            (video.status === 'not_downloaded' || video.status === 'file_missing') && !video.gone
          "
          variant="primary"
          icon="download"
          @press="ui.run(videos.mirror(video.id))"
        >
          {{
            video.status === 'file_missing' ? t('channel.list.mirrorAgain') : t('details.mirror')
          }}
        </AppButton>
        <a
          :href="details.url"
          target="_blank"
          rel="noopener"
          class="inline-flex min-h-11 items-center gap-2 rounded-md border border-line-strong px-4 text-text hover:bg-surface-raised"
        >
          {{ t('details.openOnYouTube') }}
        </a>
      </div>
      <p v-if="video.published_at === null" class="text-meta">
        <DateLabel
          :text="dateOf(video).text"
          :approximate="dateOf(video).approximate"
          :state="dateOf(video).state"
          :note="dateOf(video).note"
        />
      </p>
      <section v-if="facts.length > 0" class="flex flex-col gap-2" data-details-file>
        <h3 class="text-label font-medium text-text-muted uppercase">
          {{ t('details.file') }}
        </h3>
        <dl class="flex flex-col gap-1 text-meta">
          <div v-for="row in facts" :key="row.key" class="flex gap-4" :data-fact="row.key">
            <dt class="w-30 flex-none text-text-muted">{{ row.label }}</dt>
            <dd class="min-w-0 break-all text-text">{{ row.value }}</dd>
          </div>
        </dl>
      </section>
      <section class="flex flex-col gap-2">
        <h3 class="text-label font-medium text-text-muted uppercase">
          {{ t('details.description') }}
        </h3>
        <p class="text-meta whitespace-pre-line text-text" data-details-description>
          {{ details.description ?? t('details.noDescription') }}
        </p>
      </section>
      <section v-if="details.chapters.length > 0" class="flex flex-col gap-2">
        <h3 class="text-label font-medium text-text-muted uppercase">
          {{ t('details.chapterList') }}
        </h3>
        <ol class="flex flex-col gap-1 text-meta" data-details-chapters>
          <li v-for="chapter in details.chapters" :key="chapter.start_s" class="flex gap-3">
            <span class="w-12 flex-none text-text-muted">{{
              formatDuration(Math.round(chapter.start_s))
            }}</span>
            <span class="text-text">{{ chapter.title }}</span>
          </li>
        </ol>
      </section>
    </template>
  </aside>
</template>
