/**
 * The channels store: every channel the user added, as the sidebar and the
 * channel page show it (R-CH-34, R-CH-35), and what belongs to all of them:
 * the library and its disk (R-UI-01), the channel that was open last
 * (R-UI-02), the pause of YouTube (R-ER-05), how far a check of all channels
 * is (R-CH-20) and how the optional API key stands (R-DT-12).
 *
 * It is filled from `/api/state` and kept current by the `channel.updated`,
 * `task.progress`, `banner.changed`, `checks.progress` and `apikey.changed`
 * events, which the app store passes on. The key itself never reaches the
 * window's state: it is sent once, when it is saved or tested.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import {
  type AutoMirrorAnswer,
  api,
  type AddedChannel,
  type ApiKey,
  type ApiKeyTest,
  type Counted,
  type RepairedDates,
  type AppState,
  type Channel,
  type ChannelLookup,
  type CheckKind,
  type CheckTrigger,
  type ChosenFolder,
  type NewChannel,
  type Pause,
  type Progress,
  type FilesToTrash,
  type RemovedChannel,
} from '@/api/client'

import { useQueueStore } from './queue'
import { useViewStore } from './view'

export const useChannelsStore = defineStore('channels', () => {
  const channels = ref<Channel[]>([])
  /** The channel that was open when the app was last used, or null. */
  const lastOpenId = ref<string | null>(null)
  const libraryFolder = ref('')
  const disk = ref<AppState['disk'] | null>(null)
  /** Whether the folder dialog of macOS can be shown: only with an app window. */
  const canChooseFolder = ref(false)
  const youtubePause = ref<Pause | null>(null)
  /** How the optional API key stands (R-DT-12). Never the key itself. */
  const apiKey = ref<ApiKey>({ status: 'none', until: null })
  /** How far a check of all channels is: "Checking channels: 3 of 5" (R-CH-20). */
  const checkingAll = ref<Counted | null>(null)
  /** True once the first snapshot arrived. */
  const loaded = ref(false)

  const byId = computed(() => new Map(channels.value.map((channel) => [channel.id, channel])))

  function take(state: AppState): void {
    channels.value = state.channels
    lastOpenId.value = state.open_channel_id
    libraryFolder.value = state.library_folder
    disk.value = state.disk
    canChooseFolder.value = state.can_choose_folder
    youtubePause.value = state.youtube_pause
    apiKey.value = state.api_key
    checkingAll.value = state.checking_all ?? null
    useQueueStore().setSummary(state.queue)
    useViewStore().setView(state.view)
    loaded.value = true
  }

  /** Load the snapshot of the app. Throws an ApiError when the backend refuses. */
  async function load(): Promise<void> {
    take(await api.getState())
  }

  /**
   * Take over a channel as an event or an answer tells it.
   *
   * @returns Whether its catalogue may have changed: it was checked since, or
   *   the channel is new here. The list of its videos must then be loaded again.
   */
  function apply(channel: Channel): boolean {
    const index = channels.value.findIndex((known) => known.id === channel.id)
    const before = channels.value[index]
    if (before === undefined) {
      channels.value.push(channel)
      return true
    }
    channels.value[index] = channel
    // The version grows with every stored check. Times are whole seconds and cannot tell.
    return before.catalogue_version !== channel.catalogue_version
  }

  /** Take over how far a first listing or a full check has come. */
  function applyProgress(progress: Progress): void {
    channels.value = channels.value.map((channel) =>
      channel.id === progress.channel_id ? { ...channel, progress } : channel,
    )
  }

  /** Take over the pause of YouTube, or its end. */
  function setPause(pause: Pause | null): void {
    youtubePause.value = pause
  }

  /** Look up the channel the user named, for the preview of the dialog (R-CH-03). */
  function lookUp(text: string): Promise<ChannelLookup> {
    return api.lookUpChannel(text)
  }

  /** Ask for the video count of a preview. It is null when there is none (R-CH-03). */
  async function previewVideoCount(channelId: string): Promise<number | null> {
    try {
      return await api.getPreviewVideoCount(channelId)
    } catch {
      return null
    }
  }

  /** Show the folder dialog of macOS. The folder is null after Cancel (R-CH-05). */
  function chooseFolder(): Promise<ChosenFolder> {
    return api.chooseFolder()
  }

  /** Add a channel that was looked up. The answer says when it existed already (R-CH-04). */
  async function add(channel: NewChannel): Promise<AddedChannel> {
    const added = await api.addChannel(channel)
    // An event may have told about the channel already, and what it told is newer.
    if (!byId.value.has(added.channel.id)) {
      apply(added.channel)
    }
    return added
  }

  /** Remove a channel with its catalogue, and its files or not (R-CH-32). */
  async function remove(channelId: string, keepFiles = true): Promise<RemovedChannel> {
    const removed = await api.removeChannel(channelId, keepFiles)
    channels.value = channels.value.filter((channel) => channel.id !== channelId)
    if (lastOpenId.value === channelId) {
      lastOpenId.value = null
    }
    return removed
  }

  /** Ask what "Delete the files" would move to the Trash (R-CH-32). */
  async function filesToTrash(channelId: string): Promise<FilesToTrash> {
    return api.getFilesToTrash(channelId)
  }

  /** Pause or resume a channel (R-CH-31). */
  async function setPaused(channelId: string, paused: boolean): Promise<void> {
    apply(await api.setChannelPaused(channelId, paused))
  }

  /** Turn auto-mirror of a channel on or off (R-MI-02). It may ask first (D-095). */
  async function setAutoMirror(channelId: string, on: boolean): Promise<void> {
    apply(await api.setAutoMirror(channelId, on))
  }

  /** Answer the question before a large start of auto-mirror (D-095). */
  async function answerAutoMirror(channelId: string, answer: AutoMirrorAnswer): Promise<void> {
    apply(await api.answerAutoMirror(channelId, answer))
  }

  /** Queue every video of a channel without a file, once (R-MI-04). */
  async function mirrorMissing(channelId: string): Promise<void> {
    await api.mirrorMissing(channelId)
  }

  /** Queue the missing files of a channel again, and nothing else (R-MI-06, D-092). */
  async function mirrorThemAgain(channelId: string): Promise<void> {
    await api.mirrorThemAgain(channelId)
  }

  /** Leave the missing files of a channel missing, until more are missing (D-092). */
  async function leaveMissing(channelId: string): Promise<void> {
    apply(await api.leaveMissing(channelId))
  }

  /**
   * Start a quick or a full check of a channel (R-CH-23). That the channel is
   * being checked, and what the check found, arrives with the events: the
   * answer of this call can be older than they are.
   */
  async function check(channelId: string, kind: CheckKind, trigger: CheckTrigger): Promise<void> {
    await api.checkChannel(channelId, kind, trigger)
  }

  /** Cancel the full check of a channel (R-CH-27). */
  async function cancelCheck(channelId: string): Promise<void> {
    await api.cancelCheck(channelId)
  }

  /** Take over how the API key stands, as an event or an answer tells it. */
  function setApiKey(key: ApiKey): void {
    apiKey.value = key
  }

  /** Take over how far a check of all channels is. */
  function setCheckingAll(progress: Counted | null): void {
    checkingAll.value = progress
  }

  /** Save an API key in place of the saved one (R-DT-12). */
  async function saveApiKey(key: string): Promise<void> {
    apiKey.value = await api.saveApiKey(key)
  }

  /** Remove the API key: exact dates are looked up without it (R-DT-12). */
  async function removeApiKey(): Promise<void> {
    apiKey.value = await api.removeApiKey()
  }

  /** Ask the YouTube API once with a key, or with the saved one when none is given. */
  async function testApiKey(key: string | null): Promise<ApiKeyTest> {
    const tested = await api.testApiKey(key)
    apiKey.value = tested.api_key
    return tested
  }

  /** Compare the dates of a channel's files and repair them (R-DT-09). */
  function repairDates(channelId: string): Promise<RepairedDates> {
    return api.repairDates(channelId)
  }

  /** Start a quick check of every channel that is not paused (R-CH-23). */
  async function checkAll(): Promise<void> {
    await api.checkAllChannels()
  }

  /** Show the folder of a channel in Finder (R-CH-30). */
  async function openFolder(channelId: string): Promise<void> {
    await api.openChannelFolder(channelId)
  }

  /** Remember which channel is open, for the next start (R-UI-02). */
  async function rememberOpen(channelId: string | null): Promise<void> {
    lastOpenId.value = channelId
    await api.setOpenChannel(channelId)
  }

  /** End the pause of YouTube because the user asked for it (R-ER-05). */
  async function tryYouTubeNow(): Promise<void> {
    take(await api.tryYouTubeNow())
  }

  return {
    channels,
    lastOpenId,
    libraryFolder,
    disk,
    canChooseFolder,
    youtubePause,
    apiKey,
    checkingAll,
    loaded,
    byId,
    load,
    apply,
    applyProgress,
    setPause,
    lookUp,
    previewVideoCount,
    chooseFolder,
    add,
    remove,
    filesToTrash,
    setPaused,
    setAutoMirror,
    answerAutoMirror,
    mirrorMissing,
    mirrorThemAgain,
    leaveMissing,
    check,
    cancelCheck,
    checkAll,
    openFolder,
    rememberOpen,
    tryYouTubeNow,
    setApiKey,
    setCheckingAll,
    saveApiKey,
    removeApiKey,
    testApiKey,
    repairDates,
  }
})
