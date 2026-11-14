<script setup lang="ts">
/**
 * One inline stroke icon from the app's one icon set (docs/DESIGN.md section 3, rule 8).
 *
 * The icon takes the text colour of its parent and is hidden from screen
 * readers: an icon never carries meaning alone, a text label always goes with it.
 * It comes in three sizes, which are steps of the spacing scale: 12, 16 and 20 px.
 */
import { computed } from 'vue'

import { ICONS, type IconName } from './icons'

const props = withDefaults(
  defineProps<{
    /** Which icon to draw. */
    name: IconName
    /** How large it is: 12 px, 16 px or 20 px. */
    size?: 'sm' | 'md' | 'lg'
  }>(),
  { size: 'lg' },
)

const SIZES = { sm: 'size-3', md: 'size-4', lg: 'size-5' } as const
const sizeClass = computed(() => SIZES[props.size])
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
    class="flex-none"
    :class="sizeClass"
    :data-icon="name"
  >
    <path v-for="path in ICONS[name]" :key="path" :d="path" />
  </svg>
</template>
