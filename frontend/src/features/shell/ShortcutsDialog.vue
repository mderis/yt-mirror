<script setup lang="ts">
/**
 * The list of keyboard shortcuts (R-UI-13, R-NA-09, design: Shortcuts.html).
 *
 * It follows the table of docs/DESIGN.md section 7.3: the menu bar is the
 * source of truth, so "Check channel now" is Cmd+R, and Cmd+N, Cmd+W and
 * Cmd+Q are listed with it. Exclude (X) arrives with milestone M6 and Settings
 * (Cmd+,) with M7.
 */
import { useI18n } from 'vue-i18n'

import AppButton from '@/components/AppButton.vue'
import AppDialog from '@/components/AppDialog.vue'

const emit = defineEmits<{
  /** The list closed. */
  close: []
}>()

const { t } = useI18n()

/** The groups of the list: each shortcut as its keys and what it does. */
const GROUPS: readonly { title: string; rows: readonly [readonly string[], string][] }[] = [
  {
    title: 'shortcuts.navigation',
    rows: [
      [['↑', '↓'], 'shortcuts.move'],
      [['1 … 9'], 'shortcuts.switchChannel'],
      [['/'], 'shortcuts.filter'],
      [['G'], 'shortcuts.toggleView'],
      [['Enter'], 'shortcuts.details'],
      [['Esc'], 'shortcuts.closePanel'],
    ],
  },
  {
    title: 'shortcuts.actions',
    rows: [
      [['Space'], 'shortcuts.select'],
      [['Shift', 'Click'], 'shortcuts.range'],
      [['⌘', 'A'], 'shortcuts.selectAll'],
      [['M'], 'shortcuts.mirror'],
      [['P'], 'shortcuts.play'],
      [['F'], 'shortcuts.reveal'],
      [['⌘', 'R'], 'shortcuts.checkNow'],
    ],
  },
  {
    title: 'shortcuts.app',
    rows: [
      [['⌘', 'N'], 'shortcuts.addChannel'],
      [['⌘', 'W'], 'shortcuts.closeWindow'],
      [['⌘', 'Q'], 'shortcuts.quit'],
      [['?'], 'shortcuts.list'],
    ],
  },
]
</script>

<template>
  <AppDialog
    :title="t('shortcuts.title')"
    :close-label="t('shortcuts.close')"
    data-dialog="shortcuts"
    @close="emit('close')"
  >
    <div class="flex flex-col gap-4">
      <section v-for="group in GROUPS" :key="group.title" class="flex flex-col gap-1">
        <h3 class="font-medium">{{ t(group.title) }}</h3>
        <dl class="grid grid-cols-2 gap-x-6 gap-y-1">
          <template v-for="[keys, text] in group.rows" :key="text">
            <dt class="text-text-muted">{{ t(text) }}</dt>
            <dd class="flex items-center gap-1">
              <kbd
                v-for="key in keys"
                :key="key"
                class="rounded-xs border border-line-strong bg-surface-raised px-2 text-meta"
                >{{ key }}</kbd
              >
            </dd>
          </template>
        </dl>
      </section>
      <p class="text-meta text-text-muted">{{ t('shortcuts.note') }}</p>
    </div>
    <template #actions>
      <AppButton variant="primary" @press="emit('close')">{{ t('shortcuts.close') }}</AppButton>
    </template>
  </AppDialog>
</template>
