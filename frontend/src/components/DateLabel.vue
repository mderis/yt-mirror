<script setup lang="ts">
/**
 * The date of a video (R-DT-04, R-DT-13, docs/DESIGN.md section 8.2).
 *
 * An exact date is plain text. A date that is not exact looks like a
 * placeholder that is being replaced: dimmed text, an icon for its state and
 * a tooltip that says what the state is, never told by colour alone. From
 * milestone M2 the one state is "waiting". Milestone M4 adds "updating" and
 * "unavailable".
 */
import AppIcon from './AppIcon.vue'

withDefaults(
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
</script>

<template>
  <span v-if="!approximate" class="text-text-dim" data-date="exact">{{ text }}</span>
  <span
    v-else
    class="inline-flex items-center gap-1 text-text-muted opacity-80"
    data-date="waiting"
    :title="note"
  >
    <AppIcon name="clock" size="sm" />
    <span>{{ text }}</span>
    <span v-if="note" class="sr-only">{{ note }}</span>
  </span>
</template>
