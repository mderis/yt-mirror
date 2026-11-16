<script setup lang="ts">
/**
 * The date of a video (R-DT-04, R-DT-13, docs/DESIGN.md section 8.2).
 *
 * An exact date is plain text. A date that is not exact looks like a
 * placeholder that is being replaced: dimmed text, an icon for its state and
 * a tooltip that says what the state is, never told by colour alone. From
 * milestone M2 the one state is "waiting". Milestone M4 adds "updating" and
 * "unavailable". When the exact date arrives, it takes the place of the
 * approximate one with a short highlight that fades (R-DT-13, from milestone
 * M3). With "reduce motion" nothing moves.
 */
import { ref, watch } from 'vue'

import AppIcon from './AppIcon.vue'

const props = withDefaults(
  defineProps<{
    /** The date as text, for example "11 Nov 2026", "around 2005" or "date pending". */
    text: string
    /** False for an exact date. */
    approximate?: boolean
    /** What the state means, as the tooltip and for screen readers. */
    note?: string | undefined
  }>(),
  { approximate: false, note: undefined },
)

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
    data-date="waiting"
    :title="note"
  >
    <AppIcon name="clock" size="sm" />
    <span>{{ text }}</span>
    <span v-if="note" class="sr-only">{{ note }}</span>
  </span>
</template>
