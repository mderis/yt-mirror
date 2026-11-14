<script setup lang="ts">
/**
 * One inline stroke icon from the app's one icon set (docs/DESIGN.md section 3, rule 8).
 *
 * The icon takes the text colour of its parent and is hidden from screen
 * readers: an icon never carries meaning alone, a text label always goes with it.
 */
export type IconName = 'check' | 'download' | 'clock' | 'warning' | 'retry'

defineProps<{
  /** Which icon to draw. */
  name: IconName
}>()
</script>

<template>
  <svg
    aria-hidden="true"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    class="size-5 flex-none"
    :data-icon="name"
  >
    <path v-if="name === 'check'" d="M5 12l5 5L20 7" />
    <template v-else-if="name === 'download'">
      <path d="M12 4v11" />
      <path d="M7 11l5 5 5-5" />
      <path d="M5 20h14" />
    </template>
    <template v-else-if="name === 'clock'">
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v4l3 2" />
    </template>
    <template v-else-if="name === 'warning'">
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
      <path d="M10.3 3.9L2.5 17.5a2 2 0 0 0 1.7 3h15.6a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
    </template>
    <template v-else>
      <path d="M20 12a8 8 0 1 1-2.3-5.7" />
      <path d="M20 4v5h-5" />
    </template>
  </svg>
</template>
