<script setup lang="ts">
/**
 * The videos of a channel as a list or a grid (R-CH-10, R-UI-03, design:
 * Main.html and WebGrid.html), in the order the toolbar chose.
 *
 * From 200 videos on it is virtual (R-UI-07): only the lines in view, and a
 * few around them, are drawn, so a channel of 5,000 videos scrolls smoothly.
 * A line is one row of the list, or one row of cards of the grid; its height
 * is measured from the first one drawn. A smaller channel has every video in
 * the page. The scrolling element is the region of the page around it.
 * Every item says its place among all of them to screen readers.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'

import type { Video, ViewKind } from '@/api/client'

import VideoListItem from './VideoListItem.vue'
import { useVideoRows } from './videoRows'

const props = defineProps<{
  /** The shown videos, in their order. */
  videos: readonly Video[]
  /** The channel they belong to. */
  channelId: string
  /** List or grid. */
  view: ViewKind
  /** The element that scrolls the list. */
  scroller: HTMLElement | null
}>()

const { t } = useI18n()
const rows = useVideoRows(() => props.videos)
const shown = computed(() => props.videos.map((video) => video.id))

/** The narrowest card of the grid, in CSS pixels; more room gives more columns. */
const CARD_MIN = 240
/** Lines drawn beyond the visible ones, above and below. */
const OVERSCAN = 6
/** From this many videos on, only the lines in view are drawn. */
const VIRTUAL_FROM = 200
/** The height of a line before one was measured. */
const GUESS = { list: 89, grid: 300 }

const box = ref<HTMLElement | null>(null)
const top = ref(0)
const height = ref(800)
const width = ref(1000)
const measured = ref<number | null>(null)

const columns = computed(() =>
  props.view === 'grid' ? Math.max(1, Math.floor(width.value / CARD_MIN)) : 1,
)
const lineHeight = computed(() => measured.value ?? GUESS[props.view])
const lineCount = computed(() => Math.ceil(rows.value.length / columns.value))
const virtual = computed(() => rows.value.length >= VIRTUAL_FROM)
const first = computed(() =>
  virtual.value ? Math.max(0, Math.floor(top.value / lineHeight.value) - OVERSCAN) : 0,
)
const last = computed(() =>
  virtual.value
    ? Math.min(lineCount.value, Math.ceil((top.value + height.value) / lineHeight.value) + OVERSCAN)
    : lineCount.value,
)
/** The lines in view, each with its videos and the place of its first one. */
const lines = computed(() => {
  const drawn: { key: string; start: number; rows: typeof rows.value }[] = []
  for (let line = first.value; line < last.value; line += 1) {
    const start = line * columns.value
    const part = rows.value.slice(start, start + columns.value)
    drawn.push({ key: part[0]?.video.id ?? String(line), start, rows: part })
  }
  return drawn
})
const before = computed(() => first.value * lineHeight.value)
const after = computed(() => Math.max(0, (lineCount.value - last.value) * lineHeight.value))

function follow(): void {
  const scroller = props.scroller
  if (scroller === null) {
    return
  }
  const offset = box.value ? box.value.offsetTop : 0
  top.value = Math.max(0, scroller.scrollTop - offset)
  // A document without layout (a test) has no height: then a screenful is drawn.
  height.value = scroller.clientHeight || 800
  width.value = box.value?.clientWidth ?? scroller.clientWidth
}

/** Measure a line once one is drawn, as a row and a card differ in height. */
async function measure(): Promise<void> {
  await nextTick()
  const line = box.value?.querySelector<HTMLElement>('[data-line]')
  if (line && line.offsetHeight > 0) {
    measured.value = line.offsetHeight
  }
}

let observer: ResizeObserver | null = null

function attach(scroller: HTMLElement | null, old?: HTMLElement | null): void {
  old?.removeEventListener('scroll', follow)
  observer?.disconnect()
  if (scroller !== null) {
    scroller.addEventListener('scroll', follow, { passive: true })
    // Every browser the window runs has it; a test document may not.
    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(follow)
      observer.observe(scroller)
    }
  }
  follow()
}

watch(() => props.scroller, attach)
watch(
  () => props.view,
  () => {
    measured.value = null
    void measure()
  },
)
watch(
  () => rows.value.length,
  () => {
    follow()
    if (measured.value === null) {
      void measure()
    }
  },
)

onMounted(() => {
  attach(props.scroller)
  void measure()
})

onBeforeUnmount(() => {
  props.scroller?.removeEventListener('scroll', follow)
  observer?.disconnect()
})
</script>

<template>
  <div
    ref="box"
    role="list"
    :aria-label="t('channel.list.label')"
    :data-view="view"
    :data-count="rows.length"
    :class="view === 'grid' ? 'p-4' : undefined"
  >
    <div aria-hidden="true" :style="{ height: `${before}px` }" />
    <template v-if="view === 'list'">
      <template v-for="line in lines" :key="line.key">
        <VideoListItem
          v-for="row in line.rows"
          :key="row.video.id"
          :row="row"
          :channel-id="channelId"
          :shown="shown"
          :aria-setsize="rows.length"
          :aria-posinset="line.start + 1"
          data-line
        />
      </template>
    </template>
    <template v-else>
      <div
        v-for="line in lines"
        :key="line.key"
        class="grid gap-3 pb-3"
        :style="{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }"
        role="presentation"
        data-line
      >
        <VideoListItem
          v-for="(row, index) in line.rows"
          :key="row.video.id"
          :row="row"
          :channel-id="channelId"
          :shown="shown"
          grid
          :aria-setsize="rows.length"
          :aria-posinset="line.start + index + 1"
        />
      </div>
    </template>
    <div aria-hidden="true" :style="{ height: `${after}px` }" />
  </div>
</template>
