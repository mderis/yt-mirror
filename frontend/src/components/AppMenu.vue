<script setup lang="ts">
/**
 * A menu of actions (docs/DESIGN.md sections 4 and 8.1). It is opened by a
 * right-click and by a visible "More actions" button, so it can always be
 * reached by keyboard: the arrow keys move through the items, Home and End
 * jump, Enter chooses, Escape and Tab close it.
 *
 * An item that leaves the app is a link that opens in the default browser
 * (docs/ARCHITECTURE.md section 7.8). The menu shows only what can be done:
 * an item without a target is not passed in.
 */
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import AppIcon from './AppIcon.vue'
import type { IconName } from './icons'

/** One item of a menu. */
export interface MenuItem {
  /** What is passed on when the item is chosen. */
  id: string
  /** The words of the item: a verb. */
  label: string
  /** An icon in front of the words. */
  icon?: IconName
  /** True for a destructive action. */
  danger?: boolean
  /** An address outside the app. The item is then a link. */
  href?: string
}

const props = defineProps<{
  /** The accessible name of the menu. */
  label: string
  /** The items, in the order they are shown. */
  items: readonly MenuItem[]
  /** Where the menu opens, in the window. Without it, it opens under its parent. */
  at?: { x: number; y: number } | undefined
}>()

const emit = defineEmits<{
  /** The user chose an item. */
  choose: [id: string]
  /** The menu should close: Escape, Tab, a click elsewhere, or after a choice. */
  close: []
}>()

const menu = ref<HTMLElement | null>(null)
let focusedBefore: Element | null = null

function entries(): HTMLElement[] {
  return [...(menu.value?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [])]
}

function focusEntry(index: number): void {
  const all = entries()
  all[(index + all.length) % all.length]?.focus()
}

function onKeydown(event: KeyboardEvent): void {
  const current = entries().indexOf(document.activeElement as HTMLElement)
  const moves: Record<string, () => void> = {
    ArrowDown: () => focusEntry(current + 1),
    ArrowUp: () => focusEntry(current - 1),
    Home: () => focusEntry(0),
    End: () => focusEntry(-1),
    Escape: () => emit('close'),
    Tab: () => emit('close'),
  }
  const move = moves[event.key]
  if (move) {
    if (event.key !== 'Tab') {
      event.preventDefault()
    }
    event.stopPropagation()
    move()
  }
}

function choose(item: MenuItem): void {
  emit('choose', item.id)
  emit('close')
}

function onPointerDownElsewhere(event: Event): void {
  if (menu.value && !menu.value.contains(event.target as Node)) {
    emit('close')
  }
}

onMounted(async () => {
  focusedBefore = document.activeElement
  document.addEventListener('mousedown', onPointerDownElsewhere)
  await nextTick()
  focusEntry(0)
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onPointerDownElsewhere)
  if (focusedBefore instanceof HTMLElement) {
    focusedBefore.focus()
  }
})

const ITEM =
  'flex h-9 w-full items-center gap-2 rounded-sm px-3 text-left text-body whitespace-nowrap outline-none hover:bg-surface focus-visible:bg-surface'
</script>

<template>
  <div
    ref="menu"
    role="menu"
    :aria-label="label"
    class="z-30 flex min-w-56 flex-col rounded-lg border border-line-strong bg-surface-raised p-1 shadow-raised"
    :class="props.at ? 'fixed' : 'absolute top-full right-0 mt-1'"
    :style="props.at ? { left: `${props.at.x}px`, top: `${props.at.y}px` } : undefined"
    @keydown="onKeydown"
  >
    <template v-for="item in items" :key="item.id">
      <a
        v-if="item.href"
        role="menuitem"
        tabindex="-1"
        target="_blank"
        rel="noreferrer"
        :href="item.href"
        :class="[ITEM, item.danger ? 'text-err-text' : 'text-text']"
        @click="choose(item)"
      >
        <AppIcon v-if="item.icon" :name="item.icon" size="md" />
        {{ item.label }}
      </a>
      <button
        v-else
        type="button"
        role="menuitem"
        tabindex="-1"
        :class="[ITEM, item.danger ? 'text-err-text' : 'text-text']"
        @click="choose(item)"
      >
        <AppIcon v-if="item.icon" :name="item.icon" size="md" />
        {{ item.label }}
      </button>
    </template>
  </div>
</template>
