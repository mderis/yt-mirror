<script setup lang="ts">
/**
 * The guide of the optional YouTube API key (R-DT-12, design: ApiKeyGuide.html):
 * the steps to get a free key, a field to paste it, "Test key", "Save key",
 * "Remove key" and "Not now". It says how a saved key stands: saved, saved but
 * cannot be read, refused, or out of quota and until when. The key is sent to
 * the app once, when it is tested or saved, and never shown again: the field
 * starts empty. It opens only when the user asks for it, never by itself.
 * Milestone M7 shows the same on the settings screen.
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import type { ErrorCode } from '@/api/client'
import AppButton from '@/components/AppButton.vue'
import AppDialog from '@/components/AppDialog.vue'
import TextField from '@/components/TextField.vue'
import { formatTime } from '@/format'
import { clock } from '@/format/clock'
import { useChannelsStore } from '@/stores/channels'
import { useUiStore } from '@/stores/ui'

const emit = defineEmits<{
  /** The user is done with the guide. */
  close: []
}>()

const { t } = useI18n()
const channels = useChannelsStore()
const ui = useUiStore()

const CONSOLE = 'https://console.cloud.google.com/'
const STEPS = ['console', 'project', 'enable', 'create', 'restrict'] as const

const key = ref('')
const busy = ref<'test' | 'save' | 'remove' | null>(null)
/** The answer of the last test: true, or the code of what failed. */
const tested = ref<true | ErrorCode | null>(null)

const saved = computed(() => channels.apiKey.status !== 'none')
const statusText = computed(() => {
  const state = channels.apiKey
  if (state.status === 'none') {
    return null
  }
  if (state.status === 'quota_exceeded') {
    const until = state.until === null ? '' : formatTime(state.until, clock.timeZone)
    return t('apiKey.status.quota_exceeded', { time: until })
  }
  return t(`apiKey.status.${state.status}`)
})
const failing = computed(() =>
  ['unreadable', 'invalid', 'quota_exceeded'].includes(channels.apiKey.status),
)
const testText = computed(() => {
  if (tested.value === null) {
    return null
  }
  if (tested.value === true) {
    return t('apiKey.works')
  }
  const known: readonly ErrorCode[] = ['API_KEY_INVALID', 'API_QUOTA_EXCEEDED']
  return t(`apiKey.tested.${known.includes(tested.value) ? tested.value.toLowerCase() : 'other'}`)
})

async function test(): Promise<void> {
  busy.value = 'test'
  tested.value = null
  const pasted = key.value.trim()
  await ui.run(
    channels.testApiKey(pasted === '' ? null : pasted).then((answer) => {
      tested.value = answer.works ? true : (answer.error_code ?? 'INTERNAL')
    }),
  )
  busy.value = null
}

async function save(): Promise<void> {
  busy.value = 'save'
  if (await ui.run(channels.saveApiKey(key.value.trim()))) {
    key.value = ''
    emit('close')
  }
  busy.value = null
}

async function remove(): Promise<void> {
  busy.value = 'remove'
  await ui.run(channels.removeApiKey())
  tested.value = null
  busy.value = null
}
</script>

<template>
  <AppDialog :title="t('apiKey.title')" :close-label="t('apiKey.close')" @close="emit('close')">
    <div class="flex flex-col gap-4" data-dialog="api-key">
      <p>{{ t('apiKey.intro') }}</p>
      <div class="rounded-md bg-surface-raised p-3">
        <p class="font-medium">{{ t('apiKey.freeTitle') }}</p>
        <p class="text-meta">{{ t('apiKey.freeText') }}</p>
      </div>
      <ol class="flex flex-col gap-3">
        <li v-for="(step, index) in STEPS" :key="step" class="flex gap-3">
          <span class="font-medium text-text-muted">{{ index + 1 }}</span>
          <div class="flex flex-col gap-1">
            <p class="font-medium">{{ t(`apiKey.steps.${step}.title`) }}</p>
            <p class="text-meta">{{ t(`apiKey.steps.${step}.text`) }}</p>
            <a
              v-if="step === 'console'"
              :href="CONSOLE"
              target="_blank"
              rel="noopener"
              class="text-meta text-accent underline"
              >{{ t('apiKey.steps.console.link') }}</a
            >
          </div>
        </li>
        <li class="flex gap-3">
          <span class="font-medium text-text-muted">{{ STEPS.length + 1 }}</span>
          <div class="flex flex-1 flex-col gap-2">
            <TextField
              v-model="key"
              :label="t('apiKey.steps.paste.title')"
              :hint="saved ? t('apiKey.savedHint') : undefined"
              data-field="api-key"
            />
            <div class="flex items-center gap-3">
              <AppButton
                :busy="busy === 'test'"
                :disabled="key.trim() === '' && !saved"
                data-action="test-key"
                @press="test"
              >
                {{ t('apiKey.test') }}
              </AppButton>
              <p
                v-if="testText"
                role="status"
                class="text-meta"
                :class="tested === true ? 'text-ok-text' : 'text-err-text'"
                data-key-test
              >
                {{ testText }}
              </p>
            </div>
          </div>
        </li>
      </ol>
      <p
        v-if="statusText"
        class="text-meta"
        :class="failing ? 'text-err-text' : 'text-text-muted'"
        :role="failing ? 'alert' : undefined"
        :data-key-status="channels.apiKey.status"
      >
        {{ statusText }}
      </p>
      <p class="text-meta text-text-muted">{{ t('apiKey.stored') }}</p>
    </div>
    <template #actions>
      <AppButton
        v-if="saved"
        variant="ghost"
        :busy="busy === 'remove'"
        data-action="remove-key"
        @press="remove"
      >
        {{ t('apiKey.remove') }}
      </AppButton>
      <AppButton variant="ghost" @press="emit('close')">{{ t('apiKey.notNow') }}</AppButton>
      <AppButton
        variant="primary"
        :busy="busy === 'save'"
        :disabled="key.trim() === ''"
        data-action="save-key"
        @press="save"
      >
        {{ t('apiKey.save') }}
      </AppButton>
    </template>
  </AppDialog>
</template>
