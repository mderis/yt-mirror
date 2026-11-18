import { describe, expect, it } from 'vitest'

import { inTab, shownVideos, tabCounts } from '@/features/channel/shown'

import { NOW, video } from '../helpers/catalogue'

const exact = (number: number, changes = {}) =>
  video(number, { published_precision: null, published_around: null, ...changes })

describe('the videos a channel shows', () => {
  it('R-UI-04: each tab counts its videos', () => {
    const videos = [
      exact(1, { status: 'synced' }),
      exact(2, { status: 'failed' }),
      exact(3, { is_new: true }),
      exact(4, { status: 'queued' }),
    ]

    expect(tabCounts(videos)).toEqual({
      all: 4,
      new: 1,
      not_downloaded: 2,
      synced: 1,
      failed: 1,
    })
    expect(inTab(exact(4, { status: 'queued' }), 'not_downloaded')).toBe(true)
  })

  it('R-UI-05: the search keeps the titles that have the text, whatever its case', () => {
    const videos = [exact(1, { title: 'Restoring a workbench' }), exact(2, { title: 'Tools' })]

    expect(shownVideos(videos, 'all', '  WORKBENCH ', 'newest').map((v) => v.title)).toEqual([
      'Restoring a workbench',
    ])
  })

  it('R-UI-06: with exact dates, newest and oldest follow the dates', () => {
    const videos = [exact(1, { published_at: NOW - 100 }), exact(2, { published_at: NOW })]

    expect(shownVideos(videos, 'all', '', 'newest').map((v) => v.id)).toEqual([
      video(2).id,
      video(1).id,
    ])
    expect(shownVideos(videos, 'all', '', 'oldest').map((v) => v.id)).toEqual([
      video(1).id,
      video(2).id,
    ])
  })

  it('R-UI-06, R-DT-04: while any date is approximate, dates follow the place on the channel', () => {
    const videos = [
      exact(1, { published_at: NOW - 100 }),
      video(2, { published_at: null, published_around: NOW, published_precision: 'week' }),
      exact(3, { published_at: NOW }),
    ]

    expect(shownVideos(videos, 'all', '', 'newest').map((v) => v.id)).toEqual(
      videos.map((v) => v.id),
    )
  })

  it('R-UI-06: title, duration and size order the videos', () => {
    const videos = [
      exact(1, { title: 'B', duration_s: 10, file_size: 5 }),
      exact(2, { title: 'A', duration_s: 30, file_size: 1 }),
    ]

    expect(shownVideos(videos, 'all', '', 'title').map((v) => v.title)).toEqual(['A', 'B'])
    expect(shownVideos(videos, 'all', '', 'duration').map((v) => v.title)).toEqual(['A', 'B'])
    expect(shownVideos(videos, 'all', '', 'size').map((v) => v.title)).toEqual(['B', 'A'])
  })
})
