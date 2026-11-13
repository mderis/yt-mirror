<script setup lang="ts">
/**
 * The yt-mirror mark, drawn from the one source file icon.svg (docs/DESIGN.md section 5).
 *
 * The icon takes its colours from the accent and on-accent tokens, so it
 * follows the theme. Give it a size with a utility class such as `size-12`.
 */
import iconSource from './icon.svg?raw'

defineProps<{
  /** The accessible name. Leave it out when the icon sits next to the app name. */
  label?: string
}>()
</script>

<template>
  <!-- eslint-disable vue/no-v-html -- the markup is our own file, bundled at build time -->
  <span
    class="inline-block [&>svg]:block [&>svg]:size-full"
    :role="label ? 'img' : undefined"
    :aria-label="label"
    :aria-hidden="label ? undefined : 'true'"
    v-html="iconSource"
  />
  <!-- eslint-enable vue/no-v-html -->
</template>
