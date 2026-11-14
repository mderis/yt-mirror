<script setup lang="ts">
/**
 * A group of radio buttons with its legend (docs/DESIGN.md section 4): one
 * choice out of a few, each with room for a line of explanation. What belongs
 * to one option only, such as a date for it, goes into the `extra` slot.
 */
import { useId } from 'vue'

defineProps<{
  /** The value of the chosen option. */
  modelValue: string
  /** What the choice is about. */
  legend: string
  /** The options, in the order they are shown. */
  options: readonly { value: string; label: string; hint?: string }[]
}>()

defineEmits<{
  /** Another option was chosen. */
  'update:modelValue': [value: string]
}>()

const name = useId()
</script>

<template>
  <fieldset class="flex min-w-0 flex-col">
    <legend class="mb-1 font-medium text-text">{{ legend }}</legend>
    <div v-for="option in options" :key="option.value" class="flex flex-col">
      <label class="flex min-h-11 cursor-pointer items-start gap-3 py-1">
        <input
          type="radio"
          class="mt-1 size-5 flex-none accent-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          :name="name"
          :value="option.value"
          :checked="modelValue === option.value"
          @change="$emit('update:modelValue', option.value)"
        />
        <span class="flex min-w-0 flex-col">
          <span class="text-text">{{ option.label }}</span>
          <span v-if="option.hint" class="text-meta text-text-muted">{{ option.hint }}</span>
        </span>
      </label>
      <div v-if="modelValue === option.value && $slots.extra" class="pb-2 pl-8">
        <slot name="extra" :option="option.value" />
      </div>
    </div>
  </fieldset>
</template>
