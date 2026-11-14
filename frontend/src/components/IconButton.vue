<script setup lang="ts">
/**
 * A button that shows only an icon (docs/DESIGN.md section 4). Its label is
 * its accessible name and its tooltip, so it is never an icon without words.
 * It is 44 px square, or 36 px in a dense toolbar (section 2.7).
 */
import { computed } from 'vue'

import AppIcon from './AppIcon.vue'
import type { IconName } from './icons'

const props = withDefaults(
  defineProps<{
    /** The icon. */
    icon: IconName
    /** What the button does, for screen readers and as the tooltip. */
    label: string
    /** 44 px, or 36 px for dense places. */
    size?: 'md' | 'sm'
    /** True while what the button started is still running (R-UI-11). */
    busy?: boolean
  }>(),
  { size: 'md', busy: false },
)

const sizeClass = computed(() => (props.size === 'md' ? 'size-11' : 'size-9'))

defineEmits<{
  /** The user pressed the button. */
  press: []
}>()
</script>

<template>
  <button
    type="button"
    class="inline-flex flex-none items-center justify-center rounded-md text-text-muted duration-fast hover:bg-surface-raised hover:text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-50"
    :class="sizeClass"
    :aria-label="label"
    :title="label"
    :disabled="busy"
    :aria-busy="busy ? 'true' : undefined"
    @click="$emit('press')"
  >
    <AppIcon :name="icon" />
  </button>
</template>
