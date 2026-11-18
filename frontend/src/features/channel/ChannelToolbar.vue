<script setup lang="ts">
/**
 * The tools above the videos of a channel (design: Main.html): "select all
 * shown" (R-MI-07), the filter tabs with their counts (R-UI-04), the search by
 * title (R-UI-05), the order (R-UI-06) and the toggle of list and grid (R-UI-03).
 *
 * The tabs are toggle buttons in a labelled group; the one shown is pressed.
 * Excluded arrives with milestone M6.
 */
import { computed, useId } from 'vue'
import { useI18n } from 'vue-i18n'

import type { Video } from '@/api/client'
import AppCheckbox from '@/components/AppCheckbox.vue'
import AppIcon from '@/components/AppIcon.vue'
import IconButton from '@/components/IconButton.vue'
import SelectField from '@/components/SelectField.vue'
import { formatNumber } from '@/format'
import { useUiStore } from '@/stores/ui'
import { useViewStore } from '@/stores/view'

import { SORTS, TABS, tabCounts, type Sort } from './shown'

const props = defineProps<{
  /** Every video of the channel, as it is now, for the counts of the tabs. */
  videos: readonly Video[]
  /** The videos that are shown, in their order. */
  shown: readonly string[]
}>()

const { t } = useI18n()
const view = useViewStore()
const ui = useUiStore()
const searchId = useId()

const counts = computed(() => tabCounts(props.videos))
const sortOptions = computed(() =>
  SORTS.map((sort) => ({ value: sort, label: t(`channel.tools.sorts.${sort}`) })),
)
const allSelected = computed(
  () => props.shown.length > 0 && props.shown.every((id) => view.selected.has(id)),
)
const someSelected = computed(
  () => !allSelected.value && props.shown.some((id) => view.selected.has(id)),
)
</script>

<template>
  <div class="flex flex-wrap items-center gap-3 border-t border-line px-4 py-2" data-toolbar>
    <AppCheckbox
      :model-value="allSelected"
      :indeterminate="someSelected"
      :label="t('channel.list.selectAll')"
      hide-label
      :disabled="shown.length === 0"
      @update:model-value="view.toggleAll(shown)"
    />
    <div
      class="flex flex-wrap items-center gap-1"
      role="group"
      :aria-label="t('channel.tools.tabsLabel')"
      data-tabs
    >
      <button
        v-for="tab in TABS"
        :key="tab"
        type="button"
        class="inline-flex h-9 items-center gap-2 rounded-md px-3 text-body"
        :class="
          view.tab === tab
            ? 'bg-surface-raised font-medium text-text'
            : 'text-text-muted hover:text-text'
        "
        :aria-pressed="view.tab === tab"
        :data-tab="tab"
        @click="view.tab = tab"
      >
        {{ t(`channel.tools.tab.${tab}`) }}
        <span class="text-meta text-text-muted">{{ formatNumber(counts[tab]) }}</span>
      </button>
    </div>
    <div class="relative ml-auto min-w-40 flex-1 basis-40">
      <label :for="searchId" class="sr-only">{{ t('channel.tools.search') }}</label>
      <AppIcon
        name="search"
        class="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-text-muted"
      />
      <input
        :id="searchId"
        v-model="view.search"
        type="search"
        class="h-9 w-full rounded-md border border-line-strong bg-surface pr-3 pl-9 text-body text-text focus:outline-2 focus:outline-offset-2 focus:outline-accent"
        :placeholder="t('channel.tools.search')"
        data-search
      />
    </div>
    <SelectField
      class="w-44"
      :model-value="view.sort"
      :label="t('channel.tools.sort')"
      :options="sortOptions"
      label-hidden
      @update:model-value="(value: string) => (view.sort = value as Sort)"
    />
    <div class="flex items-center gap-1">
      <IconButton
        icon="list"
        :label="t('channel.tools.list')"
        :aria-pressed="view.view === 'list'"
        @press="ui.run(view.chooseView('list'))"
      />
      <IconButton
        icon="grid"
        :label="t('channel.tools.grid')"
        :aria-pressed="view.view === 'grid'"
        @press="ui.run(view.chooseView('grid'))"
      />
    </div>
  </div>
</template>
