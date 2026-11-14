<script setup lang="ts">
/**
 * One video in the list view (R-CH-10, docs/DESIGN.md section 4): thumbnail
 * with the duration, title, a line of facts and the status.
 *
 * The facts go into the `facts` slot and the status into the `status` slot.
 * In milestone M2 a row is read-only: selecting and the actions of a row
 * arrive with the milestones that build them.
 */
import { ref } from 'vue'

import AppBadge from './AppBadge.vue'

withDefaults(
  defineProps<{
    /** The title of the video. */
    title: string
    /** The address of the thumbnail picture, or none. */
    thumbnail?: string | undefined
    /** The duration as text, for example "24:18", or none. */
    duration?: string | undefined
    /** The word of the "new" tag. None hides it (R-CH-15). */
    newTag?: string | undefined
  }>(),
  { thumbnail: undefined, duration: undefined, newTag: undefined },
)

/** A picture that is not cached yet makes room for the plain block behind it. */
const pictureFailed = ref(false)
</script>

<template>
  <div role="listitem" class="flex items-center gap-3 border-b border-line px-4 py-2">
    <div class="relative h-18 w-32 flex-none overflow-hidden rounded-md bg-track">
      <img
        v-if="thumbnail && !pictureFailed"
        :src="thumbnail"
        alt=""
        loading="lazy"
        decoding="async"
        class="size-full object-cover"
        @error="pictureFailed = true"
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
        <span class="truncate text-title-sm font-medium text-text" data-title>{{ title }}</span>
      </div>
      <div class="flex flex-wrap items-center gap-x-2 text-meta text-text-muted" data-facts>
        <slot name="facts" />
      </div>
    </div>
    <slot name="status" />
  </div>
</template>
