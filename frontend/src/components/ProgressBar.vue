<script setup lang="ts">
/**
 * A progress bar (docs/DESIGN.md section 4).
 *
 * `value` goes from 0 to 1, and the bar fills with it. Without a value the
 * share is unknown but the work runs: a short part of the bar moves across it
 * (full, dimmed and still under "reduce motion"), and a screen reader hears
 * only the label. A thin bar is the one of a video row (design: Main.html).
 */
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    /** The share that is done, from 0 to 1, or null when it is unknown. */
    value: number | null
    /** What is progressing, for screen readers. */
    label: string
    /** Whether the bar is the thin one of a row. */
    thin?: boolean
  }>(),
  { thin: false },
)

const percent = computed(() =>
  props.value === null ? null : Math.round(Math.min(Math.max(props.value, 0), 1) * 100),
)
</script>

<template>
  <div
    role="progressbar"
    class="overflow-hidden rounded-full bg-track"
    :class="thin ? 'h-1' : 'h-2'"
    :aria-label="label"
    aria-valuemin="0"
    aria-valuemax="100"
    :aria-valuenow="percent ?? undefined"
  >
    <div v-if="percent === null" class="h-full rounded-full bg-warn animate-working" data-working />
    <div
      v-else
      class="h-full rounded-full bg-warn transition-all duration-base"
      :style="{ width: `${percent}%` }"
    />
  </div>
</template>
