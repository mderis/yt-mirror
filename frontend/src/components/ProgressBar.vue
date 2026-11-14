<script setup lang="ts">
/**
 * A progress bar (docs/DESIGN.md section 4).
 *
 * `value` goes from 0 to 1. Without a value the progress is unknown: the bar
 * is full and dimmed, and a screen reader hears only the label.
 */
import { computed } from 'vue'

const props = defineProps<{
  /** The share that is done, from 0 to 1, or null when it is unknown. */
  value: number | null
  /** What is progressing, for screen readers. */
  label: string
}>()

const percent = computed(() =>
  props.value === null ? null : Math.round(Math.min(Math.max(props.value, 0), 1) * 100),
)
</script>

<template>
  <div
    role="progressbar"
    class="h-2 overflow-hidden rounded-full bg-track"
    :aria-label="label"
    aria-valuemin="0"
    aria-valuemax="100"
    :aria-valuenow="percent ?? undefined"
  >
    <div
      class="h-2 rounded-full bg-warn duration-base"
      :class="{ 'opacity-50': percent === null }"
      :style="{ width: `${percent ?? 100}%` }"
    />
  </div>
</template>
