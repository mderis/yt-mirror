<script setup lang="ts">
/**
 * The menu of a video (R-UI-09, design: Menus.html, docs/DESIGN.md section 8.1).
 *
 * It opens by a right-click on a row or a card, at the pointer, and by the
 * visible "More actions" button, under it. Its items follow the status of the
 * video and appear with their targets (D-066): a synced video offers Play,
 * Show in Finder, Details, Open on YouTube and Re-download; one without a file
 * Mirror and "Mirror first"; a waiting one "Mirror first"; a failed one Retry.
 * A video removed from YouTube offers neither Mirror nor Retry (R-CH-14). Copy
 * link (M7), Repair metadata (M8) and Exclude forever (M6) arrive later.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { Video } from '@/api/client'
import AppMenu, { type MenuItem } from '@/components/AppMenu.vue'
import { useUiStore } from '@/stores/ui'
import { useVideosStore } from '@/stores/videos'

const props = defineProps<{
  /** The video, as it is now. */
  video: Video
  /** Where the menu opens: at the pointer, or under its button when none. */
  at?: { x: number; y: number } | undefined
}>()

const emit = defineEmits<{
  /** The menu closed. */
  close: []
}>()

const { t } = useI18n()
const videos = useVideosStore()
const ui = useUiStore()

const items = computed<MenuItem[]>(() => {
  const video = props.video
  const onYouTube: MenuItem = {
    id: 'openOnYouTube',
    label: t('channel.videoMenu.openOnYouTube'),
    icon: 'external',
    href: `https://www.youtube.com/watch?v=${video.id}`,
  }
  const details: MenuItem = { id: 'details', label: t('channel.videoMenu.details'), icon: 'info' }
  const first: MenuItem = {
    id: 'mirrorFirst',
    label: t('channel.videoMenu.mirrorFirst'),
    icon: 'download',
  }
  switch (video.status) {
    case 'synced':
      return [
        { id: 'play', label: t('channel.videoMenu.play'), icon: 'play' },
        { id: 'reveal', label: t('channel.videoMenu.reveal'), icon: 'reveal' },
        details,
        onYouTube,
        ...(video.gone || video.job_id
          ? []
          : [
              {
                id: 'redownload',
                label: t('channel.videoMenu.redownload'),
                icon: 'retry',
              } as const,
            ]),
      ]
    case 'not_downloaded':
    case 'file_missing':
      return video.gone
        ? [details, onYouTube]
        : [
            { id: 'mirror', label: t('channel.videoMenu.mirror'), icon: 'download' },
            first,
            details,
            onYouTube,
          ]
    case 'queued':
      return [first, details, onYouTube]
    case 'failed':
      return video.gone
        ? [details, onYouTube]
        : [{ id: 'retry', label: t('channel.videoMenu.retry'), icon: 'retry' }, details, onYouTube]
    default:
      return [details, onYouTube]
  }
})

function choose(id: string): void {
  const videoId = props.video.id
  const actions: Record<string, () => unknown> = {
    play: () => ui.run(videos.play(videoId)),
    reveal: () => ui.run(videos.reveal(videoId)),
    details: () => ui.run(videos.openDetails(videoId)),
    mirror: () => ui.run(videos.mirror(videoId)),
    mirrorFirst: () => ui.run(videos.mirrorFirst(videoId)),
    redownload: () => ui.run(videos.redownload([videoId])),
    retry: () => ui.run(videos.retry(videoId)),
  }
  // "Open on YouTube" is a link: the browser opens it, nothing is left to do here.
  void actions[id]?.()
}
</script>

<template>
  <AppMenu
    :label="t('channel.videoMenu.label', { title: video.title })"
    :items="items"
    :at="at"
    @choose="choose"
    @close="emit('close')"
  />
</template>
