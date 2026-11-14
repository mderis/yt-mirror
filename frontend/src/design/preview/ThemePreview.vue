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

import AppBanner from '@/components/AppBanner.vue'
import AppButton from '@/components/AppButton.vue'
import AppIcon, { type IconName } from '@/components/AppIcon.vue'
import ProgressBar from '@/components/ProgressBar.vue'

import { BrandIcon } from '../brand'
import { THEME_NAMES } from '../themes'
import { groupOf, parseTokens, shortName, TOKEN_GROUPS, type TokenGroup } from '../tokens'
import tokensCss from '../tokens.css?raw'

const ICONS: IconName[] = ['check', 'download', 'clock', 'warning', 'retry']

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
              <AppIcon v-for="icon in ICONS" :key="icon" :name="icon" />
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
          </div>
        </section>
      </section>
    </div>
  </div>
</template>
