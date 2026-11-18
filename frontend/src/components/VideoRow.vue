<script setup lang="ts">
/**
 * One video in the list view (R-CH-10, docs/DESIGN.md section 4): thumbnail
 * with the duration, title, a line of facts and the status.
 *
 * The checkbox of the selection goes into the `select` slot (R-MI-07), the
 * facts into `facts`, a progress bar into `progress`, the status into
 * `status` and the buttons into `actions`. The title is a button that opens
 * the details of the video (R-UI-08); the row of the open video and the rows
 * that are selected are marked. A right-click asks for the menu of the video
 * (R-UI-09, docs/DESIGN.md section 8.1).
 */
import { ref, watch } from 'vue'

import AppBadge from './AppBadge.vue'

const props = withDefaults(
  defineProps<{
    /** The title of the video. */
    title: string
    /** The address of the thumbnail picture, or none. */
    thumbnail?: string | undefined
    /** The duration as text, for example "24:18", or none. */
    duration?: string | undefined
    /** The word of the "new" tag. None hides it (R-CH-15). */
    newTag?: string | undefined
    /** What the title button says to a screen reader: it opens the details. None: plain text. */
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

/** A picture that is not cached yet makes room for the plain block behind it. */
const pictureFailed = ref(false)

function onPictureError(): void {
  pictureFailed.value = true
  emit('pictureMissing')
}

// Another address is another try: the picture may be cached by now.
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
    class="flex items-center gap-3 border-b border-line px-4 py-2"
    :class="{ 'bg-surface-raised': open || selected }"
    :data-open="open || undefined"
    :data-selected="selected || undefined"
    @contextmenu.prevent="emit('menu', { x: $event.clientX, y: $event.clientY })"
  >
    <slot name="select" />
    <div class="relative h-18 w-32 flex-none overflow-hidden rounded-md bg-track">
      <!-- `loading` stands before `src`: WebKit loads at once when the address is set first. -->
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
    </div>
    <div class="flex min-w-0 flex-1 flex-col gap-1">
      <div class="flex min-w-0 items-center gap-2">
        <AppBadge v-if="newTag" shape="tag">{{ newTag }}</AppBadge>
        <button
          v-if="detailsLabel"
          type="button"
          class="min-w-0 truncate rounded-xs text-left text-title-sm font-medium text-text hover:underline"
          :aria-label="detailsLabel"
          :aria-expanded="open"
          data-title
          @click="emit('details')"
        >
          {{ title }}
        </button>
        <span v-else class="truncate text-title-sm font-medium text-text" data-title>{{
          title
        }}</span>
      </div>
      <div class="flex flex-wrap items-center gap-x-2 text-meta text-text-muted" data-facts>
        <slot name="facts" />
      </div>
      <slot name="progress" />
    </div>
    <slot name="status" />
    <slot name="actions" />
  </div>
</template>
