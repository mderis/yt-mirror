<script setup lang="ts">
/**
 * One channel in the sidebar (R-CH-34, docs/DESIGN.md section 4): its avatar,
 * its name, one status line with an icon, and the count of its new videos.
 *
 * A click opens the channel. A right-click asks for its menu, which the
 * channel page also offers through a visible button (section 8.1).
 */
import { computed, ref } from 'vue'

import AppBadge from './AppBadge.vue'
import AppIcon from './AppIcon.vue'
import type { IconName } from './icons'

const props = withDefaults(
  defineProps<{
    /** The name of the channel. */
    title: string
    /** The status line, in words. */
    status: string
    /** The icon of the status. */
    statusIcon: IconName
    /** How the status line is coloured. The words and the icon carry the meaning. */
    statusTone?: 'muted' | 'progress' | 'ok' | 'failed'
    /** The address of the avatar picture, or none. */
    avatar?: string | undefined
    /** The words of the badge for new videos, for example "3 new". None hides it. */
    newVideos?: string | undefined
    /** True for the channel that is open. */
    selected?: boolean
  }>(),
  { statusTone: 'muted', avatar: undefined, newVideos: undefined, selected: false },
)

defineEmits<{
  /** The user wants to open the channel. */
  open: []
  /** The user asked for the menu of the channel, at this place of the window. */
  menu: [at: { x: number; y: number }]
}>()

const TONES = {
  muted: 'text-text-muted',
  progress: 'text-warn-text',
  ok: 'text-ok-text',
  failed: 'text-err-text',
} as const
const toneClass = computed(() => TONES[props.statusTone])

/** A picture that does not load makes room for the plain circle behind it. */
const pictureFailed = ref(false)
</script>

<template>
  <button
    type="button"
    class="flex min-h-14 w-full items-center gap-2 rounded-md px-2 py-1 text-left duration-fast hover:bg-surface-raised focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
    :class="{ 'bg-surface-raised': selected }"
    :aria-current="selected ? 'page' : undefined"
    @click="$emit('open')"
    @contextmenu.prevent="$emit('menu', { x: $event.clientX, y: $event.clientY })"
  >
    <span class="size-8 flex-none overflow-hidden rounded-full bg-track">
      <img
        v-if="avatar && !pictureFailed"
        :src="avatar"
        alt=""
        class="size-full object-cover"
        @error="pictureFailed = true"
      />
    </span>
    <span class="flex min-w-0 flex-1 flex-col">
      <span class="truncate text-text" :class="selected ? 'font-semibold' : 'font-medium'">
        {{ title }}
      </span>
      <span class="flex items-center gap-1 text-label" :class="toneClass" data-status>
        <AppIcon :name="statusIcon" size="sm" />
        <span class="truncate">{{ status }}</span>
      </span>
    </span>
    <AppBadge v-if="newVideos">{{ newVideos }}</AppBadge>
  </button>
</template>
