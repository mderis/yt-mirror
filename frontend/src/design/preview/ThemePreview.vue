<script setup lang="ts">
/**
 * The theme preview page. Implements R-TH-08.
 *
 * Shows every token and every shared component in every theme, side by side.
 * The token list is read from tokens.css itself, so a new token appears here
 * without any change to this file. A new shared component is added to the
 * "Shared components" section in the commit that creates it.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import AppBadge from '@/components/AppBadge.vue'
import AppBanner from '@/components/AppBanner.vue'
import AppButton from '@/components/AppButton.vue'
import AppDialog from '@/components/AppDialog.vue'
import AppIcon from '@/components/AppIcon.vue'
import AppMenu from '@/components/AppMenu.vue'
import DateLabel from '@/components/DateLabel.vue'
import EmptyState from '@/components/EmptyState.vue'
import IconButton from '@/components/IconButton.vue'
import { ICON_NAMES } from '@/components/icons'
import ProgressBar from '@/components/ProgressBar.vue'
import RadioGroup from '@/components/RadioGroup.vue'
import SelectField from '@/components/SelectField.vue'
import SidebarItem from '@/components/SidebarItem.vue'
import SkeletonBlock from '@/components/SkeletonBlock.vue'
import StatusChip from '@/components/StatusChip.vue'
import TextField from '@/components/TextField.vue'
import VideoRow from '@/components/VideoRow.vue'

import { BrandIcon } from '../brand'
import { THEME_NAMES } from '../themes'
import { groupOf, parseTokens, shortName, TOKEN_GROUPS, type TokenGroup } from '../tokens'
import tokensCss from '../tokens.css?raw'

interface TokenRow {
  name: string
  short: string
  value: string
  reducedMotion: string | undefined
}

const { t } = useI18n()
const tokens = parseTokens(tokensCss)

const columns = computed(() =>
  THEME_NAMES.map((theme) => ({
    theme,
    groups: TOKEN_GROUPS.map((group) => ({ group, rows: rowsOf(theme, group) })),
  })),
)

function rowsOf(theme: string, group: TokenGroup): TokenRow[] {
  const values = new Map([...tokens.shared, ...(tokens.themes.get(theme) ?? [])])
  return [...values]
    .filter(([name]) => groupOf(name) === group)
    .map(([name, value]) => ({
      name,
      short: shortName(name),
      value,
      reducedMotion: tokens.reducedMotion.get(name),
    }))
}

function ref(name: string): string {
  return `var(${name})`
}
</script>

<template>
  <div class="min-h-full bg-bg p-6 text-text">
    <header class="mb-6">
      <h1 class="font-heading text-heading-lg leading-heading font-semibold">
        {{ t('themePreview.title') }}
      </h1>
      <p class="text-body text-text-muted">{{ t('themePreview.intro') }}</p>
    </header>

    <div class="grid grid-flow-col auto-cols-fr gap-6">
      <section
        v-for="column in columns"
        :key="column.theme"
        :data-theme="column.theme"
        :data-testid="`theme-${column.theme}`"
        class="flex flex-col gap-6 rounded-xl border border-line bg-bg p-6 text-text"
      >
        <h2 class="font-heading text-heading-md leading-heading font-semibold">
          {{ t('themePreview.theme', { name: column.theme }) }}
        </h2>

        <section v-for="{ group, rows } in column.groups" :key="group" :data-group="group">
          <h3 class="mb-2 text-label font-medium text-text-muted uppercase">
            {{ t(`themePreview.groups.${group}`) }}
          </h3>

          <ul class="flex flex-col gap-2">
            <li
              v-for="row in rows"
              :key="row.name"
              :data-token="row.name"
              class="flex items-center gap-4 rounded-md border border-line bg-surface px-3 py-2"
            >
              <div class="flex w-56 shrink-0 flex-col">
                <code class="font-mono text-meta text-text">{{ row.short }}</code>
                <code class="font-mono text-label text-text-muted">{{ row.value }}</code>
                <span v-if="row.reducedMotion" class="text-label text-text-muted">
                  {{ t('themePreview.reducedMotion', { value: row.reducedMotion }) }}
                </span>
              </div>

              <div class="flex min-w-0 flex-1 items-center">
                <span
                  v-if="group === 'color'"
                  class="h-10 w-full rounded-sm border border-line-strong"
                  :style="{ backgroundColor: ref(row.name) }"
                />
                <span
                  v-else-if="group === 'font-size'"
                  class="truncate"
                  :style="{ fontSize: ref(row.name) }"
                  >{{ t('themePreview.sample') }}</span
                >
                <span
                  v-else-if="group === 'font-weight'"
                  class="truncate text-body-lg"
                  :style="{ fontWeight: ref(row.name) }"
                  >{{ t('themePreview.sample') }}</span
                >
                <span
                  v-else-if="group === 'font'"
                  class="truncate text-heading-sm"
                  :style="{ fontFamily: ref(row.name) }"
                  >{{ t('themePreview.sample') }}</span
                >
                <span
                  v-else-if="group === 'line-height'"
                  class="w-48 bg-surface-raised text-body"
                  :style="{ lineHeight: ref(row.name) }"
                  >{{ t('themePreview.sample') }}</span
                >
                <span v-else-if="group === 'space'" class="flex items-end gap-2">
                  <span
                    v-for="multiple in [1, 2, 4, 8]"
                    :key="multiple"
                    class="bg-accent"
                    :style="{
                      width: `calc(${ref(row.name)} * ${multiple})`,
                      height: `calc(${ref(row.name)} * ${multiple})`,
                    }"
                  />
                  <span class="text-label text-text-muted">{{ t('themePreview.spaceSteps') }}</span>
                </span>
                <span
                  v-else-if="group === 'radius'"
                  class="size-12 border border-line-strong bg-surface-raised"
                  :style="{ borderRadius: ref(row.name) }"
                />
                <span
                  v-else-if="group === 'shadow'"
                  class="m-3 h-12 w-40 rounded-lg bg-surface-raised"
                  :style="{ boxShadow: ref(row.name) }"
                />
                <span
                  v-else-if="group === 'duration'"
                  class="rounded-md bg-neutral-bg px-3 py-2 text-meta text-neutral-text transition-colors hover:bg-accent hover:text-on-accent"
                  :style="{ transitionDuration: ref(row.name) }"
                  >{{ t('themePreview.hoverMe') }}</span
                >
              </div>
            </li>
          </ul>
        </section>

        <section data-group="brand">
          <h3 class="mb-2 text-label font-medium text-text-muted uppercase">
            {{ t('themePreview.brand') }}
          </h3>
          <div class="flex items-center gap-4 rounded-md border border-line bg-surface px-3 py-2">
            <BrandIcon class="size-16" :label="t('app.name')" />
            <BrandIcon class="size-8" />
            <span class="font-heading text-heading-sm font-semibold">{{ t('app.name') }}</span>
          </div>
        </section>

        <section data-group="components">
          <h3 class="mb-2 text-label font-medium text-text-muted uppercase">
            {{ t('themePreview.components') }}
          </h3>
          <div
            class="flex flex-col gap-3 rounded-md border border-line bg-surface px-3 py-3"
            data-component="button"
          >
            <div class="flex flex-wrap items-center gap-3">
              <AppButton variant="primary">{{ t('themePreview.sampleButton') }}</AppButton>
              <AppButton icon="retry">{{ t('themePreview.sampleSecondaryButton') }}</AppButton>
              <AppButton variant="primary" disabled>
                {{ t('themePreview.sampleDisabledButton') }}
              </AppButton>
            </div>
            <div class="flex items-center gap-3 text-text-dim" data-component="icon">
              <AppIcon v-for="icon in ICON_NAMES" :key="icon" :name="icon" />
            </div>
            <div class="flex flex-col gap-2" data-component="progress">
              <ProgressBar :value="0.64" :label="t('themePreview.sampleProgress')" />
              <ProgressBar :value="null" :label="t('themePreview.sampleProgress')" />
            </div>
            <AppBanner data-component="banner">
              {{ t('themePreview.sampleBanner') }}
              <template #action>
                <AppButton icon="download">{{ t('themePreview.sampleBannerAction') }}</AppButton>
              </template>
            </AppBanner>
            <AppBanner tone="error">{{ t('themePreview.sampleErrorBanner') }}</AppBanner>
            <AppBanner tone="info">{{ t('themePreview.sampleInfoBanner') }}</AppBanner>
            <div class="flex flex-wrap items-center gap-3" data-component="more-buttons">
              <AppButton variant="ghost">{{ t('themePreview.sampleGhostButton') }}</AppButton>
              <AppButton variant="danger" icon="trash">
                {{ t('themePreview.sampleDangerButton') }}
              </AppButton>
              <IconButton icon="more" :label="t('themePreview.sampleIconButton')" />
              <IconButton icon="retry" size="sm" :label="t('themePreview.sampleSecondaryButton')" />
            </div>
            <div class="flex flex-wrap items-center gap-2" data-component="chip">
              <StatusChip>{{ t('themePreview.sampleChips.plain') }}</StatusChip>
              <StatusChip tone="neutral" icon="clock">
                {{ t('themePreview.sampleChips.neutral') }}
              </StatusChip>
              <StatusChip tone="progress" icon="download">
                {{ t('themePreview.sampleChips.progress') }}
              </StatusChip>
              <StatusChip tone="ok" icon="check">{{ t('themePreview.sampleChips.ok') }}</StatusChip>
              <StatusChip tone="failed" icon="warning">
                {{ t('themePreview.sampleChips.failed') }}
              </StatusChip>
              <AppBadge>{{ t('themePreview.sampleBadge') }}</AppBadge>
              <AppBadge shape="tag">{{ t('themePreview.sampleTag') }}</AppBadge>
            </div>
            <div class="flex flex-col gap-3" data-component="field">
              <TextField
                model-value=""
                :label="t('themePreview.sampleField')"
                :placeholder="t('themePreview.samplePlaceholder')"
                :hint="t('themePreview.sampleFieldHint')"
              />
              <TextField
                model-value="https://youtu.be/abc"
                :label="t('themePreview.sampleField')"
                :error="t('themePreview.sampleFieldError')"
              />
              <SelectField
                model-value="best"
                :label="t('themePreview.sampleSelect')"
                :options="[
                  { value: 'best', label: t('themePreview.sampleSelectOptions.best') },
                  { value: '1080', label: t('themePreview.sampleSelectOptions.p1080') },
                ]"
              />
              <RadioGroup
                model-value="pick"
                :legend="t('themePreview.sampleRadio')"
                :options="[
                  {
                    value: 'pick',
                    label: t('themePreview.sampleRadioOptions.pick'),
                    hint: t('themePreview.sampleRadioOptions.pickHint'),
                  },
                  { value: 'all', label: t('themePreview.sampleRadioOptions.all') },
                ]"
              />
            </div>
            <div class="relative h-36" data-component="menu">
              <AppMenu
                class="left-0"
                :label="t('themePreview.sampleMenu')"
                :items="[
                  { id: 'check', label: t('themePreview.sampleMenuItems.check'), icon: 'retry' },
                  {
                    id: 'open',
                    label: t('themePreview.sampleMenuItems.open'),
                    icon: 'external',
                    href: '#',
                  },
                  {
                    id: 'remove',
                    label: t('themePreview.sampleMenuItems.remove'),
                    icon: 'trash',
                    danger: true,
                  },
                ]"
              />
            </div>
            <AppDialog
              inline
              data-component="dialog"
              :title="t('themePreview.sampleDialog')"
              :close-label="t('themePreview.sampleDialogClose')"
            >
              <p class="text-text-dim">{{ t('themePreview.sampleDialogBody') }}</p>
              <template #actions>
                <AppButton variant="ghost">{{ t('themePreview.sampleGhostButton') }}</AppButton>
                <AppButton variant="danger">{{ t('themePreview.sampleDangerButton') }}</AppButton>
              </template>
            </AppDialog>
            <div class="flex flex-col gap-1 bg-surface-side p-2" data-component="sidebar-item">
              <SidebarItem
                selected
                status-icon="check"
                status-tone="ok"
                :title="t('themePreview.sampleChannel')"
                :status="t('themePreview.sampleChannelStatus')"
                :new-videos="t('themePreview.sampleBadge')"
              />
              <SidebarItem
                status-icon="retry"
                status-tone="progress"
                :title="t('themePreview.sampleChannel')"
                :status="t('themePreview.sampleChannelChecking')"
              />
            </div>
            <div role="list" data-component="video-row">
              <VideoRow
                :title="t('themePreview.sampleVideo')"
                :duration="t('themePreview.sampleDuration')"
                :new-tag="t('themePreview.sampleTag')"
              >
                <template #facts>
                  <span>{{ t('themePreview.sampleUploaded') }}</span>
                  <DateLabel :text="t('themePreview.sampleExactDate')" />
                  <span>{{ t('themePreview.sampleViews') }}</span>
                </template>
                <template #status>
                  <StatusChip>{{ t('themePreview.sampleChips.plain') }}</StatusChip>
                </template>
              </VideoRow>
              <VideoRow :title="t('themePreview.sampleVideo')">
                <template #facts>
                  <span>{{ t('themePreview.sampleUploaded') }}</span>
                  <DateLabel
                    approximate
                    :text="t('themePreview.sampleAroundDate')"
                    :note="t('themePreview.sampleDateNote')"
                  />
                </template>
                <template #status>
                  <StatusChip>{{ t('themePreview.sampleChips.plain') }}</StatusChip>
                </template>
              </VideoRow>
            </div>
            <div class="flex items-center gap-3" data-component="skeleton">
              <SkeletonBlock class="h-18 w-32" />
              <div class="flex flex-1 flex-col gap-2">
                <SkeletonBlock class="h-3 w-1/2" />
                <SkeletonBlock class="h-3 w-1/4" />
              </div>
            </div>
            <EmptyState icon="video" :title="t('themePreview.sampleEmpty')" data-component="empty">
              {{ t('themePreview.sampleEmptyText') }}
            </EmptyState>
          </div>
        </section>
      </section>
    </div>
  </div>
</template>
