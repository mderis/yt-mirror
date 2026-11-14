<script setup lang="ts">
/**
 * A select with its label (docs/DESIGN.md section 4): one choice out of a short list.
 */
import { useId } from 'vue'

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
    <select
      :id="id"
      :value="modelValue"
      :aria-describedby="hint ? hintId : undefined"
      class="h-11 w-full rounded-md border border-line-strong bg-surface px-3 text-body text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      @change="$emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
    >
      <option v-for="option in options" :key="option.value" :value="option.value">
        {{ option.label }}
      </option>
    </select>
    <p v-if="hint" :id="hintId" class="mt-1 text-meta text-text-muted">{{ hint }}</p>
  </div>
</template>
