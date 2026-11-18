<script setup lang="ts">
/**
 * One video in the grid view (R-UI-03, docs/DESIGN.md section 4, design:
 * WebGrid.html and GridLight.html): the thumbnail with the duration, the
 * title, a line of facts and the status, with the same slots as the row of
 * the list: `select`, `facts`, `progress`, `status` and `actions`.
 *
 * The title is a button that opens the details (R-UI-08); a right-click asks
 * for the menu of the video (R-UI-09).
 */
import { ref, watch } from 'vue'

import AppBadge from './AppBadge.vue'

const props = withDefaults(
  defineProps<{
    /** The title of the video. */
    title: string
    /** The address of the thumbnail picture, or none. */
    thumbnail?: string | undefined
    /** The duration as text, or none. */
    duration?: string | undefined
    /** The word of the "new" tag. None hides it (R-CH-15). */
    newTag?: string | undefined
    /** What the title button says to a screen reader: it opens the details. */
    detailsLabel?: string | undefined
    /** Whether the details of this video are open. */
    open?: boolean
    /** Whether the video is selected (R-MI-07). */
    selected?: boolean
  }>(),
  {
    thumbnail: undefined,
    duration: undefined,
    newTag: undefined,
    detailsLabel: undefined,
    open: false,
    selected: false,
  },
)

const emit = defineEmits<{
  /** The thumbnail could not be loaded: it is not cached yet (R-CH-16). */
  pictureMissing: []
  /** The title was pressed: show the details of the video. */
  details: []
  /** A right-click: show the menu of the video at that place (R-UI-09). */
  menu: [at: { x: number; y: number }]
}>()

const pictureFailed = ref(false)

function onPictureError(): void {
  pictureFailed.value = true
  emit('pictureMissing')
}

watch(
  () => props.thumbnail,
  () => {
    pictureFailed.value = false
  },
)
</script>

<template>
  <div
    role="listitem"
    class="flex min-w-0 flex-col gap-2 rounded-lg border border-line p-2"
    :class="open || selected ? 'bg-surface-raised' : 'bg-surface'"
    :data-open="open || undefined"
    :data-selected="selected || undefined"
    @contextmenu.prevent="emit('menu', { x: $event.clientX, y: $event.clientY })"
  >
    <div class="relative aspect-video w-full overflow-hidden rounded-md bg-track">
      <img
        v-if="thumbnail && !pictureFailed"
        loading="lazy"
        decoding="async"
        :src="thumbnail"
        alt=""
        class="size-full object-cover"
        @error="onPictureError"
      />
      <span
        v-if="duration"
        class="absolute right-1 bottom-1 rounded-xs bg-scrim px-1 text-label text-on-scrim"
        data-duration
      >
        {{ duration }}
      </span>
      <div class="absolute top-0 left-1">
        <slot name="select" />
      </div>
    </div>
    <div class="flex min-w-0 items-start gap-2">
      <AppBadge v-if="newTag" shape="tag">{{ newTag }}</AppBadge>
      <button
        v-if="detailsLabel"
        type="button"
        class="line-clamp-2 min-w-0 rounded-xs text-left text-title-sm font-medium text-text hover:underline"
        :aria-label="detailsLabel"
        :aria-expanded="open"
        data-title
        @click="emit('details')"
      >
        {{ title }}
      </button>
      <span v-else class="line-clamp-2 text-title-sm font-medium text-text" data-title>{{
        title
      }}</span>
    </div>
    <div class="flex flex-wrap items-center gap-x-2 text-meta text-text-muted" data-facts>
      <slot name="facts" />
    </div>
    <slot name="progress" />
    <div class="mt-auto flex flex-wrap items-center justify-between gap-2">
      <slot name="status" />
      <slot name="actions" />
    </div>
  </div>
</template>
