<script setup lang="ts">
/**
 * A banner: a persistent message about an app-wide condition (docs/GLOSSARY.md,
 * R-FB-04). The message is the default slot. The action that fixes the
 * condition goes into the `action` slot.
 *
 * An `error` banner interrupts a screen reader, the others wait their turn.
 */
import { computed } from 'vue'

import AppIcon from './AppIcon.vue'

const props = withDefaults(
  defineProps<{
    /** How urgent the condition is. */
    tone?: 'attention' | 'error'
  }>(),
  { tone: 'attention' },
)

const LOOKS = {
  attention: 'bg-warn-bg text-warn-text',
  error: 'bg-err-bg text-err-text',
} as const
const ROLES = { attention: 'status', error: 'alert' } as const
const look = computed(() => LOOKS[props.tone])
const role = computed(() => ROLES[props.tone])
</script>

<template>
  <div
    class="flex flex-wrap items-center gap-3 rounded-lg px-4 py-3 text-body"
    :class="look"
    :role="role"
  >
    <AppIcon name="warning" />
    <div class="min-w-0 flex-1"><slot /></div>
    <slot name="action" />
  </div>
</template>
