<script setup lang="ts">
/**
 * A select with its label (docs/DESIGN.md section 4): one choice out of a short list.
 *
 * It is the real `<select>` of the browser, so the keyboard and the menu of
 * choices are the system's, but its arrow is drawn from tokens with the icon of
 * the app (`appearance: none`): each macOS version draws its own arrow, and not
 * for the dark theme (docs/DESIGN.md section 4, "Form controls"). Its focus ring
 * follows `:focus`, as the other form controls do.
 */
import { useId } from 'vue'

import AppIcon from './AppIcon.vue'

defineProps<{
  /** The value of the chosen option. */
  modelValue: string
  /** What the choice is about. */
  label: string
  /** The options, in the order they are shown. */
  options: readonly { value: string; label: string }[]
  /** A short explanation under the select. */
  hint?: string | undefined
}>()

defineEmits<{
  /** Another option was chosen. */
  'update:modelValue': [value: string]
}>()

const id = useId()
const hintId = useId()
</script>

<template>
  <div class="flex min-w-0 flex-col">
    <label :for="id" class="mb-1 font-medium text-text">{{ label }}</label>
    <div class="relative">
      <select
        :id="id"
        :value="modelValue"
        :aria-describedby="hint ? hintId : undefined"
        class="h-11 w-full cursor-pointer appearance-none rounded-md border border-line-strong bg-surface pr-10 pl-3 text-body text-text hover:border-accent focus:outline-2 focus:outline-offset-2 focus:outline-accent"
        @change="$emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
      >
        <option v-for="option in options" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
      <AppIcon
        name="chevron"
        class="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-text-muted"
        data-arrow
      />
    </div>
    <p v-if="hint" :id="hintId" class="mt-1 text-meta text-text-muted">{{ hint }}</p>
  </div>
</template>
