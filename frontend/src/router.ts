/**
 * The pages of the app and their addresses (docs/ARCHITECTURE.md section 2).
 *
 * The app uses the part of the address behind `#`, so the local server needs
 * no rule for deep links (docs/DECISIONS.md D-063). Tests pass a history
 * that lives in memory.
 */
import {
  createRouter,
  createWebHashHistory,
  type Router,
  type RouteLocationRaw,
  type RouterHistory,
} from 'vue-router'

import ChannelPage from '@/features/channel/ChannelPage.vue'
import WelcomePage from '@/features/welcome/WelcomePage.vue'

/** The address of the page of a channel. */
export function channelRoute(channelId: string): RouteLocationRaw {
  return { name: 'channel', params: { id: channelId } }
}

export function createAppRouter(history: RouterHistory = createWebHashHistory()): Router {
  return createRouter({
    history,
    routes: [
      { path: '/', name: 'home', component: WelcomePage },
      { path: '/channels/:id', name: 'channel', component: ChannelPage, props: true },
      { path: '/:rest(.*)*', redirect: { name: 'home' } },
    ],
  })
}
