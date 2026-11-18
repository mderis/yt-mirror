<script setup lang="ts">
/**
 * A checkbox with its label (docs/DESIGN.md section 4): one switch on its own,
 * as auto-mirror in the channel header, or the selection of a video (R-MI-07).
 *
 * It is a real `<input type="checkbox">` in its label, so the keyboard (Space),
 * screen readers and forms behave as the system's. It is drawn from tokens, not
 * by the system (`appearance: none`): it looks the same on every macOS and in
 * every theme. Like the radio group, its focus ring follows `:focus`, because
 * WebKit does not always show `:focus-visible` for form controls. It can be
 * mixed (`indeterminate`), as "select all shown" is when only some are selected.
 * A click tells whether Shift was held, for the range of R-MI-07.
 */
import { onMounted, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    /** Whether it is ticked. */
    modelValue: boolean
    /** What it switches. Read by screen readers also when it is hidden. */
    label: string
    /** Whether the label is for screen readers only, as on a row of the list. */
    hideLabel?: boolean
    /** Whether it shows as mixed: some of what it stands for is ticked. */
    indeterminate?: boolean
    /** Whether it cannot be changed. */
    disabled?: boolean
    /** A short explanation next to the label. */
    hint?: string | undefined
  }>(),
  { hideLabel: false, indeterminate: false, disabled: false, hint: undefined },
)

const emit = defineEmits<{
  /** It was ticked or unticked. */
  'update:modelValue': [value: boolean]
  /** It was clicked, with whether Shift was held (R-MI-07: a range). */
  pick: [value: boolean, shift: boolean]
}>()

const box = ref<HTMLInputElement | null>(null)

function sync(): void {
  if (box.value) box.value.indeterminate = props.indeterminate
}

onMounted(sync)
watch(() => props.indeterminate, sync)

function clicked(event: MouseEvent): void {
  if (props.disabled) return
  const value = (event.target as HTMLInputElement).checked
  emit('update:modelValue', value)
  emit('pick', value, event.shiftKey)
}
</script>

<template>
  <label
    class="inline-flex min-h-11 items-center gap-3"
    :class="disabled ? 'cursor-not-allowed' : 'cursor-pointer'"
  >
    <input
      ref="box"
      type="checkbox"
      class="size-5 flex-none focus:outline-2 focus:outline-offset-2 focus:outline-accent"
      :checked="modelValue"
      :disabled="disabled"
      :aria-checked="indeterminate ? 'mixed' : modelValue"
      @click="clicked"
    />
    <span :class="hideLabel ? 'sr-only' : 'flex min-w-0 flex-col'">
      <span :class="disabled ? 'text-text-muted' : 'text-text'">{{ label }}</span>
      <span v-if="hint && !hideLabel" class="text-meta text-text-muted">{{ hint }}</span>
    </span>
  </label>
</template>

<style scoped>
/* The box: a frame, filled with the accent and a check mark when ticked. Tokens only. */
[type='checkbox'] {
  appearance: none;
  position: relative;
  border: calc(var(--ytm-space) / 2) solid var(--ytm-color-text-muted);
  border-radius: var(--ytm-radius-xs);
  background-color: var(--ytm-color-surface);
  cursor: inherit;
  transition-property: border-color, background-color;
  transition-duration: var(--ytm-duration-fast);
}

[type='checkbox']:hover:not(:disabled, :checked, :indeterminate) {
  border-color: var(--ytm-color-accent);
}

[type='checkbox']:checked,
[type='checkbox']:indeterminate {
  border-color: var(--ytm-color-accent);
  background-color: var(--ytm-color-accent);
}

/* The check mark: two sides of a rotated frame, in the colour on the accent. */
[type='checkbox']:checked::after {
  content: '';
  position: absolute;
  left: calc(var(--ytm-space) * 1.25);
  top: calc(var(--ytm-space) / 2);
  width: calc(var(--ytm-space) * 1.25);
  height: calc(var(--ytm-space) * 2.5);
  border: solid var(--ytm-color-on-accent);
  border-width: 0 calc(var(--ytm-space) / 2) calc(var(--ytm-space) / 2) 0;
  transform: rotate(45deg);
}

/* Mixed: a bar across. */
[type='checkbox']:indeterminate::after {
  content: '';
  position: absolute;
  left: calc(var(--ytm-space) * 0.75);
  right: calc(var(--ytm-space) * 0.75);
  top: calc(50% - var(--ytm-space) / 4);
  height: calc(var(--ytm-space) / 2);
  background-color: var(--ytm-color-on-accent);
}

[type='checkbox']:disabled {
  border-color: var(--ytm-color-line-strong);
  background-color: var(--ytm-color-neutral-bg);
}

[type='checkbox']:disabled:checked,
[type='checkbox']:disabled:indeterminate {
  background-color: var(--ytm-color-line-strong);
}

/* macOS "Increase contrast": the frame takes the colour of the text. */
@media (prefers-contrast: more) {
  [type='checkbox']:not(:checked, :indeterminate, :disabled) {
    border-color: var(--ytm-color-text);
  }

  [type='checkbox']:disabled {
    border-color: var(--ytm-color-text-muted);
  }
}
</style>
