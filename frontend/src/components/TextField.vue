<script setup lang="ts">
/**
 * A text field with its label (docs/DESIGN.md section 4). The label is always
 * there for screen readers. It can be hidden from view where the surrounding
 * text already says what the field is for.
 */
import { useId } from 'vue'

withDefaults(
  defineProps<{
    /** The text in the field. */
    modelValue: string
    /** What the field is for. */
    label: string
    /** True to keep the label for screen readers only. */
    hideLabel?: boolean
    /** A short explanation under the field. */
    hint?: string | undefined
    /** What is wrong with the text, shown in place of the hint. */
    error?: string | undefined
    /** Text shown while the field is empty. */
    placeholder?: string | undefined
    /** A text or a date. */
    type?: 'text' | 'date'
    /** True while the field cannot be used. */
    disabled?: boolean
    /** True to give this field the focus when a dialog opens. */
    autofocus?: boolean
  }>(),
  {
    hideLabel: false,
    hint: undefined,
    error: undefined,
    placeholder: undefined,
    type: 'text',
    disabled: false,
    autofocus: false,
  },
)

defineEmits<{
  /** The text changed. */
  'update:modelValue': [value: string]
  /** The user pressed Enter in the field. */
  enter: []
}>()

const id = useId()
const noteId = useId()
</script>

<template>
  <div class="flex min-w-0 flex-col">
    <label :for="id" class="mb-1 font-medium text-text" :class="{ 'sr-only': hideLabel }">
      {{ label }}
    </label>
    <input
      :id="id"
      :type="type"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      :data-autofocus="autofocus ? '' : undefined"
      :aria-invalid="error ? 'true' : undefined"
      :aria-describedby="error || hint ? noteId : undefined"
      class="h-11 w-full rounded-md border border-line-strong bg-surface px-3 text-body text-text placeholder:text-text-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-50"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
      @keydown.enter="$emit('enter')"
    />
    <p v-if="error" :id="noteId" class="mt-1 text-meta text-err-text" role="alert">{{ error }}</p>
    <p v-else-if="hint" :id="noteId" class="mt-1 text-meta text-text-muted">{{ hint }}</p>
  </div>
</template>
