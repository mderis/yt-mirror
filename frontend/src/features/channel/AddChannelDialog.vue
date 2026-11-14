<script setup lang="ts">
/**
 * The add channel dialog, in two steps (R-CH-01 to R-CH-06, design:
 * AddChannel1.html, AddChannel2.html, docs/DESIGN.md section 8.5).
 *
 * Step 1 takes what the user pasted and looks the channel up. Step 2 shows
 * the channel that was found and asks where to save it, in which quality,
 * and what to mirror. The video count of the preview arrives by itself and
 * is optional: without it the dialog is complete (R-CH-03).
 *
 * A folder is never typed. It is the default the backend proposes or the one
 * the folder dialog of macOS returned (docs/ARCHITECTURE.md section 9).
 */
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { ApiError, pictures, type ChannelLookup, type ErrorCode, type Quality } from '@/api/client'
import AppBanner from '@/components/AppBanner.vue'
import AppButton from '@/components/AppButton.vue'
import AppDialog from '@/components/AppDialog.vue'
import AppIcon from '@/components/AppIcon.vue'
import RadioGroup from '@/components/RadioGroup.vue'
import SelectField from '@/components/SelectField.vue'
import StatusChip from '@/components/StatusChip.vue'
import TextField from '@/components/TextField.vue'
import { formatNumber, startOfDay } from '@/format'
import { clock } from '@/format/clock'
import { useErrorTexts } from '@/i18n/errors'
import { useChannelsStore } from '@/stores/channels'

const props = defineProps<{
  /** What the user already typed, for example on the welcome screen. */
  initialText: string
}>()

const emit = defineEmits<{
  /** The user left the dialog without adding a channel. */
  close: []
  /** A channel was added, or it existed already and is to be opened (R-CH-04). */
  added: [channelId: string, existing: boolean]
}>()

const { t, te } = useI18n()
const textsOf = useErrorTexts()
const channels = useChannelsStore()

const QUALITIES = ['default', '2160', '1440', '1080', '720', '480'] as const
const UNKNOWN_ERROR: ErrorCode = 'INTERNAL'

const text = ref(props.initialText)
const lookingUp = ref(false)
const lookupError = ref<string | undefined>(undefined)
const preview = ref<ChannelLookup | null>(null)
const videoCount = ref<number | null>(null)
const avatarFailed = ref(false)
/** The folder the user chose in the folder dialog. Null means the default. */
const chosenFolder = ref<string | null>(null)
const videoFiles = ref(0)
const choosing = ref(false)
const quality = ref<string>('default')
const mirror = ref<string>('pick')
const afterDay = ref('')
const adding = ref(false)
const failure = ref<ErrorCode | null>(null)

function codeOf(error: unknown): ErrorCode {
  return error instanceof ApiError ? error.code : UNKNOWN_ERROR
}

/** Why a lookup failed, in words. What is no channel says what is accepted (R-CH-02). */
function lookupFailure(error: unknown): string {
  if (error instanceof ApiError && error.code === 'INVALID_CHANNEL_INPUT') {
    const key = `addChannel.rejected.${error.details.reason ?? ''}`
    return t(te(key) ? key : 'addChannel.rejected.other')
  }
  const texts = textsOf(codeOf(error))
  return [texts.happened, texts.action].filter(Boolean).join(' ')
}

async function lookUp(): Promise<void> {
  if (lookingUp.value || text.value.trim() === '') {
    return
  }
  lookingUp.value = true
  lookupError.value = undefined
  try {
    const found = await channels.lookUp(text.value)
    if (found.existing) {
      emit('added', found.channel_id, true)
      return
    }
    preview.value = found
    videoCount.value = null
    avatarFailed.value = false
    chosenFolder.value = null
    videoFiles.value = found.video_files
    failure.value = null
    void channels.previewVideoCount(found.channel_id).then((count) => {
      if (preview.value?.channel_id === found.channel_id) {
        videoCount.value = count
      }
    })
  } catch (error) {
    lookupError.value = lookupFailure(error)
  } finally {
    lookingUp.value = false
  }
}

async function chooseFolder(): Promise<void> {
  choosing.value = true
  failure.value = null
  try {
    const chosen = await channels.chooseFolder()
    if (chosen.folder !== null) {
      chosenFolder.value = chosen.folder
      videoFiles.value = chosen.video_files
    }
  } catch (error) {
    failure.value = codeOf(error)
  } finally {
    choosing.value = false
  }
}

const mirrorAfter = computed(() =>
  mirror.value === 'after' ? startOfDay(afterDay.value, clock.timeZone) : null,
)
const canAdd = computed(() => mirror.value !== 'after' || mirrorAfter.value !== null)

async function add(found: ChannelLookup): Promise<void> {
  adding.value = true
  failure.value = null
  try {
    const added = await channels.add({
      channel_id: found.channel_id,
      folder: chosenFolder.value,
      quality: quality.value === 'default' ? null : (quality.value as Quality),
      auto_mirror: mirror.value !== 'pick',
      mirror_after: mirrorAfter.value,
    })
    emit('added', added.channel.id, added.existing)
  } catch (error) {
    failure.value = codeOf(error)
  } finally {
    adding.value = false
  }
}

/** The handle and the video count of the preview, as far as they are known. */
const facts = computed(() => {
  const count = videoCount.value
  return [
    preview.value?.handle,
    count === null ? null : t('addChannel.videoCount', { count: formatNumber(count) }, count),
  ]
    .filter(Boolean)
    .join(` ${t('app.separator')} `)
})

const qualityOptions = computed(() =>
  QUALITIES.map((value) => ({ value, label: t(`addChannel.qualities.${value}`) })),
)

const mirrorOptions = computed(() => [
  { value: 'pick', label: t('addChannel.pick'), hint: t('addChannel.pickHint') },
  {
    value: 'all',
    label: t('addChannel.all'),
    hint:
      videoCount.value === null
        ? t('addChannel.allHintWithoutCount')
        : t('addChannel.allHint', { count: formatNumber(videoCount.value) }),
  },
  { value: 'after', label: t('addChannel.after') },
])

const failureTexts = computed(() => (failure.value ? textsOf(failure.value) : null))

onMounted(() => {
  if (props.initialText.trim() !== '') {
    void lookUp()
  }
})
</script>

<template>
  <AppDialog
    :title="t('addChannel.title')"
    :close-label="t('addChannel.close')"
    @close="emit('close')"
  >
    <template v-if="!preview">
      <TextField
        v-model="text"
        :label="t('addChannel.field')"
        :hint="t('addChannel.hint')"
        :error="lookupError"
        autofocus
        @enter="lookUp"
      />
      <p v-if="lookingUp" class="flex items-center gap-2 text-text-dim" role="status">
        <AppIcon name="retry" size="md" />
        {{ t('addChannel.lookingUp') }}
      </p>
    </template>

    <template v-else>
      <div class="flex items-center gap-3 rounded-lg border border-line bg-bg p-3" data-preview>
        <span class="size-13 flex-none overflow-hidden rounded-full bg-track">
          <img
            v-if="preview.has_avatar && !avatarFailed"
            :src="pictures.previewAvatar(preview.channel_id)"
            alt=""
            class="size-full object-cover"
            @error="avatarFailed = true"
          />
        </span>
        <div class="min-w-0 flex-1">
          <p class="truncate text-body-lg font-semibold">{{ preview.title }}</p>
          <p v-if="facts" class="text-meta text-text-muted" data-facts>{{ facts }}</p>
        </div>
        <StatusChip tone="ok" icon="check">{{ t('addChannel.found') }}</StatusChip>
      </div>

      <div>
        <p class="mb-1 font-medium">{{ t('addChannel.saveTo') }}</p>
        <div class="flex items-center gap-2">
          <p
            class="flex min-h-11 min-w-0 flex-1 items-center rounded-md border border-line-strong px-3 py-2 break-all"
            data-folder
          >
            {{ chosenFolder ?? preview.folder }}
          </p>
          <AppButton v-if="channels.canChooseFolder" :busy="choosing" @press="chooseFolder">
            {{ t('addChannel.choose') }}
          </AppButton>
        </div>
        <p class="mt-1 text-meta text-text-muted">{{ t('addChannel.folderHint') }}</p>
      </div>

      <AppBanner v-if="videoFiles > 0" tone="info" data-banner="existing-files">
        {{ t('addChannel.existingFiles', { count: formatNumber(videoFiles) }, videoFiles) }}
      </AppBanner>

      <SelectField v-model="quality" :label="t('addChannel.quality')" :options="qualityOptions" />

      <RadioGroup v-model="mirror" :legend="t('addChannel.mirror')" :options="mirrorOptions">
        <template #extra="{ option }">
          <TextField
            v-if="option === 'after'"
            v-model="afterDay"
            type="date"
            :label="t('addChannel.afterDate')"
            hide-label
          />
        </template>
      </RadioGroup>

      <p v-if="failureTexts" class="text-err-text" role="alert">
        {{ failureTexts.happened }} {{ failureTexts.action }}
      </p>
    </template>

    <template #actions>
      <template v-if="!preview">
        <AppButton variant="ghost" @press="emit('close')">{{ t('addChannel.cancel') }}</AppButton>
        <AppButton
          variant="primary"
          :disabled="text.trim() === ''"
          :busy="lookingUp"
          @press="lookUp"
        >
          {{ t('addChannel.continue') }}
        </AppButton>
      </template>
      <template v-else>
        <AppButton variant="ghost" @press="preview = null">{{ t('addChannel.back') }}</AppButton>
        <AppButton variant="primary" :disabled="!canAdd" :busy="adding" @press="add(preview)">
          {{ t('addChannel.add') }}
        </AppButton>
      </template>
    </template>
  </AppDialog>
</template>
