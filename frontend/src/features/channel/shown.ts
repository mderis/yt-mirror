/**
 * Which videos of a channel are shown, and in which order (R-UI-04 to R-UI-06).
 *
 * The tabs filter by status (R-UI-04): All, New, Not downloaded, Synced and
 * Failed; Excluded arrives with milestone M6. Search keeps the videos whose
 * title has the text, whatever its case (R-UI-05). Sorting by date never uses
 * an approximate date: while any date of the channel is approximate, newest
 * and oldest first follow the place of the videos on the channel, which is
 * exact (R-UI-06, R-DT-04).
 *
 * Plain functions: the store and the list call them with the videos as they are now.
 */
import type { Video } from '@/api/client'

/** The tabs of a channel (R-UI-04). */
export const TABS = ['all', 'new', 'not_downloaded', 'synced', 'failed'] as const
export type Tab = (typeof TABS)[number]

/** The orders of a channel (R-UI-06). */
export const SORTS = ['newest', 'oldest', 'title', 'duration', 'size'] as const
export type Sort = (typeof SORTS)[number]

/** Whether a video belongs to a tab. */
export function inTab(video: Video, tab: Tab): boolean {
  switch (tab) {
    case 'all':
      return true
    case 'new':
      return video.is_new
    case 'synced':
      return video.status === 'synced'
    case 'failed':
      return video.status === 'failed'
    case 'not_downloaded':
      return video.status !== 'synced' && video.status !== 'failed'
  }
}

/** How many videos each tab has (R-UI-04). */
export function tabCounts(videos: readonly Video[]): Record<Tab, number> {
  const counts = Object.fromEntries(TABS.map((tab) => [tab, 0])) as Record<Tab, number>
  for (const video of videos) {
    for (const tab of TABS) {
      if (inTab(video, tab)) {
        counts[tab] += 1
      }
    }
  }
  return counts
}

/** Whether the title of a video has the text that was typed, whatever its case (R-UI-05). */
export function matches(video: Video, search: string): boolean {
  const wanted = search.trim().toLocaleLowerCase()
  return wanted === '' || video.title.toLocaleLowerCase().includes(wanted)
}

/**
 * The videos of a tab that match the search, in the chosen order.
 *
 * @param videos The catalogue, in the order of the channel (newest first).
 */
export function shownVideos(
  videos: readonly Video[],
  tab: Tab,
  search: string,
  sort: Sort,
): Video[] {
  const kept = videos.filter((video) => inTab(video, tab) && matches(video, search))
  const place = new Map(videos.map((video, index) => [video.id, index]))
  const byPlace = (a: Video, b: Video): number => (place.get(a.id) ?? 0) - (place.get(b.id) ?? 0)
  switch (sort) {
    case 'newest':
    case 'oldest': {
      const ordered = anyApproximate(videos) ? kept.sort(byPlace) : kept.sort(byDate(byPlace))
      return sort === 'newest' ? ordered : ordered.reverse()
    }
    case 'title':
      return kept.sort((a, b) => a.title.localeCompare(b.title) || byPlace(a, b))
    case 'duration':
      return kept.sort((a, b) => (b.duration_s ?? -1) - (a.duration_s ?? -1) || byPlace(a, b))
    case 'size':
      return kept.sort((a, b) => (b.file_size ?? -1) - (a.file_size ?? -1) || byPlace(a, b))
  }
}

/** Whether any date of the channel is approximate or missing: then dates do not order. */
function anyApproximate(videos: readonly Video[]): boolean {
  return videos.some((video) => video.published_at === null)
}

/** Newest first by the exact date, the place on the channel between equal ones (R-DT-11). */
function byDate(byPlace: (a: Video, b: Video) => number): (a: Video, b: Video) => number {
  return (a, b) => (b.published_at ?? 0) - (a.published_at ?? 0) || byPlace(a, b)
}
