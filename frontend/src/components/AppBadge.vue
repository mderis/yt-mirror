<script setup lang="ts">
/**
 * A small badge in the "new" colour: the count of new videos of a channel as
 * a pill, or the word "New" in front of a title as a tag (R-CH-15, R-CH-34).
 * Its words are the default slot.
 */
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    /** A pill for a count, a tag for a word in front of a title. */
    shape?: 'pill' | 'tag'
  }>(),
  { shape: 'pill' },
)

const SHAPES = { pill: 'rounded-full px-2', tag: 'rounded-xs px-1 uppercase' } as const
const shapeClass = computed(() => SHAPES[props.shape])
</script>

<template>
  <span
    class="inline-flex flex-none items-center bg-warn text-label font-semibold whitespace-nowrap text-on-warn"
    :class="shapeClass"
    :data-badge="shape"
  >
    <slot />
  </span>
</template>
