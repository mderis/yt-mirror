<script setup lang="ts">
/**
 * The empty state of a list or a panel (docs/DESIGN.md section 3, rule 7): an
 * icon, a title that says what is not there, a sentence in the default slot,
 * and the way forward in the `action` slot.
 */
import AppIcon from './AppIcon.vue'
import type { IconName } from './icons'

defineProps<{
  /** What is not there. */
  title: string
  /** An icon above the title. */
  icon: IconName
}>()
</script>

<template>
  <div class="flex flex-col items-center gap-2 p-10 text-center">
    <span class="text-ok-text"><AppIcon :name="icon" /></span>
    <h2 class="font-heading text-heading-md font-semibold text-text">{{ title }}</h2>
    <p class="max-w-130 text-text-muted"><slot /></p>
    <slot name="action" />
  </div>
</template>
