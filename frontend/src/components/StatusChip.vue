<script setup lang="ts">
/**
 * A status chip (docs/DESIGN.md section 4): the status of a video or a small
 * confirmation such as "Found". A status always has its words, and where it
 * helps an icon as well, never a colour alone (section 3, rule 1).
 */
import { computed } from 'vue'

import AppIcon from './AppIcon.vue'
import type { IconName } from './icons'

const props = withDefaults(
  defineProps<{
    /** What kind of status it is. */
    tone?: 'plain' | 'neutral' | 'ok' | 'progress' | 'failed'
    /** An icon in front of the words. */
    icon?: IconName | undefined
  }>(),
  { tone: 'plain', icon: undefined },
)

const LOOKS = {
  plain: 'border border-line-strong text-text-dim',
  neutral: 'bg-neutral-bg text-neutral-text',
  ok: 'bg-ok-bg text-ok-text',
  progress: 'bg-warn-bg text-warn-text',
  failed: 'bg-err-bg text-err-text',
} as const
const look = computed(() => LOOKS[props.tone])
</script>

<template>
  <span
    class="inline-flex flex-none items-center gap-1 rounded-full px-3 py-1 text-meta whitespace-nowrap"
    :class="look"
    :data-tone="tone"
  >
    <AppIcon v-if="icon" :name="icon" size="sm" />
    <slot />
  </span>
</template>
