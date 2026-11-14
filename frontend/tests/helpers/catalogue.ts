/** Builders of channels, videos and the snapshot of the app, for tests. */
import type { AppState, Channel, Video } from '@/api/client'

/** 14 Nov 2026, 06:42:00 UTC: the "now" of the tests. */
export const NOW = 1_794_638_520
export const CHANNEL_ID = 'UCsmall000000000000000001'
export const OTHER_CHANNEL_ID = 'UCother000000000000000002'

/** Returns a channel that was listed and checked a short while ago. */
export function channel(changes: Partial<Channel> = {}): Channel {
  const id = changes.id ?? CHANNEL_ID
  return {
    id,
    url: `https://www.youtube.com/channel/${id}`,
    title: 'Sample Channel',
    handle: '@sample',
    folder: '/Users/sam/Movies/YouTube/Sample Channel',
    folder_is_custom: false,
    quality: null,
    auto_mirror: false,
    mirror_after: null,
    paused: false,
    first_listed_at: NOW - 3600,
    last_check_at: NOW - 120,
    last_full_check_at: NOW - 3600,
    last_check_error: null,
    status: 'up_to_date',
    videos: 12,
    synced: 0,
    excluded: 0,
    size_bytes: 0,
    new_videos: 0,
    progress: null,
    pictures: 1,
    ...changes,
  }
}

/** Returns video number `number` of a channel, with an exact date. */
export function video(number: number, changes: Partial<Video> = {}): Video {
  return {
    id: `video${String(number).padStart(6, '0')}`,
    title: `Video ${number}`,
    duration_s: 573,
    view_count: 48_000,
    published_at: NOW - number * 86_400,
    published_precision: null,
    published_around: null,
    status: 'not_downloaded',
    excluded: false,
    gone: false,
    is_new: false,
    ...changes,
  }
}

/** Returns the snapshot of an app, by default one without channels. */
export function appState(changes: Partial<AppState> = {}): AppState {
  return {
    channels: [],
    open_channel_id: null,
    library_folder: '/Users/sam/Movies/YouTube',
    disk: { name: 'Macintosh HD', free_bytes: 412_000_000_000 },
    can_choose_folder: true,
    youtube_pause: null,
    ...changes,
  }
}
