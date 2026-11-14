<script setup lang="ts">
/**
 * A banner: a persistent message about an app-wide condition (docs/GLOSSARY.md,
 * R-FB-04). The message is the default slot. The action that fixes the
 * condition goes into the `action` slot.
 *
 * An `error` banner interrupts a screen reader, the others wait their turn.
 * Every tone has an icon of its own, so it is never told by colour alone.
 */
import { computed } from 'vue'

import AppIcon from './AppIcon.vue'

const props = withDefaults(
  defineProps<{
    /** How urgent the condition is. `info` only tells something. */
    tone?: 'attention' | 'error' | 'info'
  }>(),
  { tone: 'attention' },
)

const LOOKS = {
  attention: 'bg-warn-bg text-warn-text',
  error: 'bg-err-bg text-err-text',
  info: 'bg-ok-bg text-ok-text',
} as const
const ROLES = { attention: 'status', error: 'alert', info: 'status' } as const
const ICON = { attention: 'warning', error: 'warning', info: 'info' } as const

const look = computed(() => LOOKS[props.tone])
const role = computed(() => ROLES[props.tone])
const icon = computed(() => ICON[props.tone])
</script>

<template>
  <div
    class="flex flex-wrap items-center gap-3 rounded-lg px-4 py-3 text-body"
    :class="look"
    :role="role"
  >
    <AppIcon :name="icon" />
    <div class="min-w-0 flex-1"><slot /></div>
    <slot name="action" />
  </div>
</template>
