<script setup lang="ts">
/**
 * The date of a video (R-DT-04, R-DT-13, docs/DESIGN.md section 8.2).
 *
 * An exact date is plain text. A date that is not exact looks like a
 * placeholder that is being replaced: dimmed text, an icon for its state and
 * a tooltip that says what the state is, never told by colour alone.
 * Waiting: a clock. Updating: a loading icon that turns. Unavailable: a
 * warning, with why and when it is tried again. When the exact date
 * arrives, it takes the place of the approximate one with a short highlight
 * that fades. With "reduce motion" nothing moves, and the icons still differ.
 */
import { computed, ref, watch } from 'vue'

import AppIcon from './AppIcon.vue'
import type { IconName } from './icons'

/** The state of a date that is not exact. */
export type DateLabelState = 'waiting' | 'updating' | 'unavailable'

const props = withDefaults(
  defineProps<{
    /** The date as text, for example "11 Nov 2026", "around 2005" or "date pending". */
    text: string
    /** False for an exact date. */
    approximate?: boolean
    /** What the state means, as the tooltip and for screen readers. */
    note?: string | undefined
    /** The state of a date that is not exact. */
    state?: DateLabelState
  }>(),
  { approximate: false, note: undefined, state: 'waiting' },
)

const ICON_OF: Record<DateLabelState, IconName> = {
  waiting: 'clock',
  updating: 'loading',
  unavailable: 'warning',
}

const icon = computed(() => ICON_OF[props.state])
/** The loading icon turns; the other two stand still. */
const motion = computed(() => (props.state === 'updating' ? 'animate-turn' : undefined))

/** Whether the exact date has just arrived and is highlighted. */
const arrived = ref(false)

watch(
  () => props.approximate,
  (now, before) => {
    arrived.value = before === true && now === false
  },
)
</script>

<template>
  <span
    v-if="!approximate"
    class="rounded-xs text-text-dim"
    :class="{ 'animate-arrive': arrived }"
    data-date="exact"
    :data-arrived="arrived || undefined"
    @animationend="arrived = false"
    >{{ text }}</span
  >
  <!-- `relative` keeps the hidden note inside this label. Without it the note is placed
       against the window and makes the window itself scrollable. -->
  <span
    v-else
    class="relative inline-flex items-center gap-1 text-text-muted"
    :data-date="state"
    :title="note"
  >
    <AppIcon :name="icon" size="sm" :class="motion" />
    <span>{{ text }}</span>
    <span v-if="note" class="sr-only">{{ note }}</span>
  </span>
</template>
