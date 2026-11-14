<script setup lang="ts">
/**
 * The one shell of the app (R-UI-01, design: Main.html): the sidebar and the
 * main area with the banners of app-wide conditions (R-FB-04) above the page.
 * It also draws what opens on top of the pages: the add channel dialog, the
 * remove channel dialog and the channel menu of a right-click.
 *
 * It decides which page is shown: the channel that was open last, or the
 * welcome screen while there is no channel (R-UI-02).
 */
import { computed, watchEffect } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterView, useRoute, useRouter } from 'vue-router'

import AppBanner from '@/components/AppBanner.vue'
import IconButton from '@/components/IconButton.vue'
import AddChannelDialog from '@/features/channel/AddChannelDialog.vue'
import ChannelMenu from '@/features/channel/ChannelMenu.vue'
import RemoveChannelDialog from '@/features/channel/RemoveChannelDialog.vue'
import ToolBanners from '@/features/tools/ToolBanners.vue'
import { useErrorTexts } from '@/i18n/errors'
import { channelRoute } from '@/router'
import { useChannelsStore } from '@/stores/channels'
import { useToolsStore } from '@/stores/tools'
import { useUiStore } from '@/stores/ui'

import AppSidebar from './AppSidebar.vue'
import YouTubePauseBanner from './YouTubePauseBanner.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const channels = useChannelsStore()
const tools = useToolsStore()
const ui = useUiStore()
const textsOf = useErrorTexts()

const menuChannel = computed(() => (ui.menu ? channels.byId.get(ui.menu.channelId) : undefined))
const removing = computed(() =>
  ui.removeChannelId ? channels.byId.get(ui.removeChannelId) : undefined,
)
const actionError = computed(() => (ui.actionError ? textsOf(ui.actionError) : null))
const hasBanners = computed(
  () =>
    tools.troubled.length > 0 ||
    tools.installing ||
    channels.youtubePause !== null ||
    ui.actionError !== null,
)

const leavingHome = computed(() => route.name === 'home' && channels.channels.length > 0)

// The page follows the channels: one that is gone is left, and "home" is a channel if there is one.
watchEffect(() => {
  if (route.name === 'channel' && !channels.byId.has(String(route.params.id))) {
    void router.replace({ name: 'home' })
  } else if (route.name === 'home' && channels.channels[0]) {
    const last = channels.lastOpenId
    const id = last !== null && channels.byId.has(last) ? last : channels.channels[0].id
    void router.replace(channelRoute(id))
  }
})

function onAdded(channelId: string, existing: boolean): void {
  ui.closeAddChannel()
  ui.noteExisting(existing ? channelId : null)
  void router.push(channelRoute(channelId))
}
</script>

<template>
  <div class="flex h-full bg-bg text-text">
    <AppSidebar />
    <div class="flex min-w-0 flex-1 flex-col">
      <div v-if="hasBanners" class="flex flex-col gap-3 px-7 pt-4" data-banners>
        <ToolBanners />
        <YouTubePauseBanner />
        <AppBanner v-if="actionError" tone="error" data-banner="action-failed">
          <p class="font-medium">{{ actionError.happened }}</p>
          <p v-if="actionError.action" class="text-meta">
            {{ actionError.doing }} {{ actionError.action }}
          </p>
          <template #action>
            <IconButton
              icon="close"
              size="sm"
              :label="t('error.dismiss')"
              @press="ui.dismissError()"
            />
          </template>
        </AppBanner>
      </div>
      <!-- While "home" is about to become the page of a channel, the welcome screen is not drawn. -->
      <RouterView v-if="!leavingHome" class="min-h-0 flex-1" />
    </div>

    <ChannelMenu
      v-if="ui.menu && menuChannel"
      :channel="menuChannel"
      :at="ui.menu.at"
      @close="ui.closeMenu()"
    />
    <AddChannelDialog
      v-if="ui.addChannelText !== null"
      :initial-text="ui.addChannelText"
      @close="ui.closeAddChannel()"
      @added="onAdded"
    />
    <RemoveChannelDialog v-if="removing" :channel="removing" @close="ui.closeRemove()" />
  </div>
</template>
