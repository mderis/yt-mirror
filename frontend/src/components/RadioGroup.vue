<script setup lang="ts">
/**
 * A group of radio buttons with its legend (docs/DESIGN.md section 4): one
 * choice out of a few, each with room for a line of explanation. What belongs
 * to one option only, such as a date for it, goes into the `extra` slot.
 *
 * Each option is a real `<input type="radio">` in its label, so the keyboard
 * (Tab into the group, arrow keys between options), screen readers and the
 * form behave as the system's. It is drawn from tokens, not by the system
 * (`appearance: none`): it looks the same on every macOS and in every theme
 * (docs/DESIGN.md section 4, "Form controls"). Its focus ring follows `:focus`,
 * as the system's radio did: WebKit drops `:focus-visible` when the arrow keys
 * move between options, and a mouse click does not focus a radio there.
 */
import { useId } from 'vue'

defineProps<{
  /** The value of the chosen option. */
  modelValue: string
  /** What the choice is about. */
  legend: string
  /** The options, in the order they are shown. A disabled one cannot be chosen. */
  options: readonly {
    value: string
    label: string
    hint?: string | undefined
    disabled?: boolean | undefined
  }[]
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
      <label
        class="flex min-h-11 items-start gap-3 py-1"
        :class="option.disabled ? 'cursor-not-allowed' : 'cursor-pointer'"
      >
        <input
          type="radio"
          class="mt-1 size-5 flex-none focus:outline-2 focus:outline-offset-2 focus:outline-accent"
          :name="name"
          :value="option.value"
          :checked="modelValue === option.value"
          :disabled="option.disabled"
          @change="$emit('update:modelValue', option.value)"
        />
        <span class="flex min-w-0 flex-col">
          <span :class="option.disabled ? 'text-text-muted' : 'text-text'">{{ option.label }}</span>
          <span v-if="option.hint" class="text-meta text-text-muted">{{ option.hint }}</span>
        </span>
      </label>
      <div v-if="modelValue === option.value && $slots.extra" class="pb-2 pl-8">
        <slot name="extra" :option="option.value" />
      </div>
    </div>
  </fieldset>
</template>

<style scoped>
/* The circle: a ring, filled with the accent and a dot when chosen. Tokens only. */
[type='radio'] {
  appearance: none;
  border: calc(var(--ytm-space) / 2) solid var(--ytm-color-text-muted);
  border-radius: var(--ytm-radius-full);
  background-color: var(--ytm-color-surface);
  cursor: inherit;
  transition-property: border-color, background-color, box-shadow;
  transition-duration: var(--ytm-duration-fast);
}

[type='radio']:hover:not(:disabled, :checked) {
  border-color: var(--ytm-color-accent);
}

[type='radio']:checked {
  border-color: var(--ytm-color-accent);
  background-color: var(--ytm-color-on-accent);
  box-shadow: inset 0 0 0 calc(var(--ytm-space) * 1.25) var(--ytm-color-accent);
}

[type='radio']:disabled {
  border-color: var(--ytm-color-line-strong);
  background-color: var(--ytm-color-neutral-bg);
}

[type='radio']:disabled:checked {
  box-shadow: inset 0 0 0 calc(var(--ytm-space) * 1.25) var(--ytm-color-line-strong);
}

/* macOS "Increase contrast": the ring takes the colour of the text. */
@media (prefers-contrast: more) {
  [type='radio']:not(:checked, :disabled) {
    border-color: var(--ytm-color-text);
  }

  [type='radio']:disabled {
    border-color: var(--ytm-color-text-muted);
  }
}
</style>
