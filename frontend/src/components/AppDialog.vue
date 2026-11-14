<script setup lang="ts">
/**
 * A dialog (docs/DESIGN.md section 3, rule 3): a title that states the question
 * or the outcome, a body, and buttons whose labels are verbs. The body is the
 * default slot, the buttons go into the `actions` slot.
 *
 * It is modal: the page behind it is covered, the Tab key stays inside it,
 * Escape closes it, and the focus returns to where it was (R-UI-14).
 */
import { nextTick, onBeforeUnmount, onMounted, ref, useId } from 'vue'

import IconButton from './IconButton.vue'

const props = withDefaults(
  defineProps<{
    /** The title of the dialog. */
    title: string
    /** The accessible name of the close button. */
    closeLabel: string
    /** True to draw the dialog in the flow of the page, as the theme preview page does. */
    inline?: boolean
  }>(),
  { inline: false },
)

const emit = defineEmits<{
  /** The user wants to leave the dialog without doing anything. */
  close: []
}>()

const titleId = useId()
const panel = ref<HTMLElement | null>(null)
let focusedBefore: Element | null = null

const CAN_TAKE_FOCUS =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

function focusable(): HTMLElement[] {
  return [...(panel.value?.querySelectorAll<HTMLElement>(CAN_TAKE_FOCUS) ?? [])]
}

/** Keep the Tab key inside the dialog, and let Escape close it. */
function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    event.stopPropagation()
    emit('close')
    return
  }
  if (event.key !== 'Tab') {
    return
  }
  const stops = focusable()
  const first = stops[0]
  const last = stops.at(-1)
  if (!first || !last) {
    return
  }
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

onMounted(() => {
  if (props.inline) {
    return
  }
  focusedBefore = document.activeElement
  // Once the dialog is on the page: the field that asks for the focus, or the dialog itself.
  void nextTick(() => {
    const wanted = panel.value?.querySelector<HTMLElement>('[data-autofocus]')
    ;(wanted ?? panel.value)?.focus()
  })
})

onBeforeUnmount(() => {
  if (focusedBefore instanceof HTMLElement) {
    focusedBefore.focus()
  }
})
</script>

<template>
  <div
    class="flex items-center justify-center p-6"
    :class="inline ? 'rounded-lg bg-scrim' : 'fixed inset-0 z-40 overflow-y-auto bg-scrim/70'"
    data-dialog-backdrop
    @mousedown.self="emit('close')"
  >
    <div
      ref="panel"
      role="dialog"
      :aria-modal="inline ? undefined : 'true'"
      :aria-labelledby="titleId"
      tabindex="-1"
      class="flex max-h-full w-full max-w-160 flex-col rounded-xl border border-line-strong bg-surface text-text shadow-overlay outline-none"
      @keydown="onKeydown"
    >
      <div class="flex items-center gap-3 px-6 pt-5 pb-3">
        <h2 :id="titleId" class="min-w-0 flex-1 font-heading text-heading-md font-semibold">
          {{ title }}
        </h2>
        <IconButton icon="close" :label="closeLabel" @press="emit('close')" />
      </div>
      <div class="flex min-h-0 flex-col gap-4 overflow-y-auto px-6 pt-1 pb-5">
        <slot />
      </div>
      <div class="flex flex-wrap items-center justify-end gap-2 border-t border-line px-6 py-4">
        <slot name="actions" />
      </div>
    </div>
  </div>
</template>
