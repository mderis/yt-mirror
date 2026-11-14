<script setup lang="ts">
/**
 * A button (docs/DESIGN.md section 4). A real `button` element, at least 44 px high.
 *
 * `primary` is the one main action of a view or dialog. `secondary` is every
 * other action. `ghost` is a quiet way out, such as Cancel. `danger` is a
 * destructive action and is never the default (section 3, rule 4). The label
 * is the default slot and is always a verb.
 */
import { computed } from 'vue'

import AppIcon from './AppIcon.vue'
import type { IconName } from './icons'

const props = withDefaults(
  defineProps<{
    /** The look of the button. */
    variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
    /** An icon in front of the label. */
    icon?: IconName | undefined
    /** True while the button cannot be used. */
    disabled?: boolean
    /** True while what the button started is still running (R-UI-11). */
    busy?: boolean
  }>(),
  { variant: 'secondary', icon: undefined, disabled: false, busy: false },
)

const LOOKS = {
  primary: 'bg-accent text-on-accent hover:opacity-90',
  secondary: 'border border-line-strong bg-transparent text-text hover:bg-surface-raised',
  ghost: 'bg-transparent text-text-muted hover:bg-surface-raised hover:text-text',
  danger: 'bg-err-bg text-err-text hover:opacity-90',
} as const
const look = computed(() => LOOKS[props.variant])

defineEmits<{
  /** The user pressed the button. */
  press: []
}>()
</script>

<template>
  <button
    type="button"
    class="inline-flex h-11 items-center justify-center gap-2 rounded-md px-4 text-body font-medium whitespace-nowrap duration-fast focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-50"
    :class="look"
    :disabled="disabled || busy"
    :aria-busy="busy ? 'true' : undefined"
    @click="$emit('press')"
  >
    <AppIcon v-if="icon" :name="icon" />
    <slot />
  </button>
</template>
