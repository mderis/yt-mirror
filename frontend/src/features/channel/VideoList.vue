<script setup lang="ts">
/**
 * The list of a channel's videos (R-CH-10, design: Main.html), in the order
 * of the channel, newest first.
 *
 * The list is not virtual before milestone M5, so it draws every row. It is
 * therefore built so that it is drawn again only when the catalogue itself
 * changes, never because something else about the channel did.
 */
import { useI18n } from 'vue-i18n'

import type { Video } from '@/api/client'

import VideoListItem from './VideoListItem.vue'
import { useVideoRows } from './videoRows'

const props = defineProps<{
  /** The videos, in the order they are shown. */
  videos: readonly Video[]
  /** The channel they belong to. */
  channelId: string
}>()

const { t } = useI18n()
const rows = useVideoRows(() => props.videos)
</script>

<template>
  <div role="list" :aria-label="t('channel.list.label')">
    <VideoListItem v-for="row in rows" :key="row.video.id" :row="row" :channel-id="channelId" />
  </div>
</template>
