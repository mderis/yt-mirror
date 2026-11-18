import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { nextTick } from 'vue'

import { useViewStore } from '@/stores/view'

const SHOWN = ['a', 'b', 'c', 'd', 'e']

describe('the selection of videos', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('R-MI-07: a checkbox selects one video, and Shift-click selects the range to it', () => {
    const view = useViewStore()

    view.pick('b', true, false, SHOWN)
    view.pick('d', true, true, SHOWN)

    expect([...view.selected].sort()).toEqual(['b', 'c', 'd'])
  })

  it('R-MI-07: Shift-click on a selected one unselects the range', () => {
    const view = useViewStore()
    view.toggleAll(SHOWN)
    view.pick('a', false, false, SHOWN)

    view.pick('c', false, true, SHOWN)

    expect([...view.selected].sort()).toEqual(['d', 'e'])
  })

  it('R-MI-07: "select all shown" selects every shown video, or none when all are', () => {
    const view = useViewStore()

    view.toggleAll(SHOWN)
    expect(view.selected.size).toBe(5)
    view.toggleAll(SHOWN)
    expect(view.selected.size).toBe(0)
  })

  it('R-MI-07, R-UI-04: another tab or search starts without a selection', async () => {
    const view = useViewStore()
    view.toggleAll(SHOWN)

    view.tab = 'synced'
    await nextTick()

    expect(view.selected.size).toBe(0)
  })
})
