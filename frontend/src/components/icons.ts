/**
 * The one icon set of the app (docs/DESIGN.md section 3, rule 8): stroke icons on a
 * 24 by 24 grid, each as the paths that draw it. `AppIcon.vue` draws them.
 */
export const ICONS = {
  check: ['M5 12l5 5L20 7'],
  download: ['M12 4v11', 'M7 11l5 5 5-5', 'M5 20h14'],
  clock: ['M12 4a8 8 0 1 0 0 16a8 8 0 0 0 0-16z', 'M12 8v4l3 2'],
  warning: [
    'M12 9v4',
    'M12 17h.01',
    'M10.3 3.9L2.5 17.5a2 2 0 0 0 1.7 3h15.6a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z',
  ],
  retry: ['M20 12a8 8 0 1 1-2.3-5.7', 'M20 4v5h-5'],
  plus: ['M12 5v14', 'M5 12h14'],
  folder: ['M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z'],
  more: ['M5 12h.01', 'M12 12h.01', 'M19 12h.01'],
  close: ['M6 6l12 12', 'M18 6L6 18'],
  pause: ['M9 5v14', 'M15 5v14'],
  resume: ['M7 5l12 7-12 7z'],
  external: ['M14 5h5v5', 'M19 5l-8 8', 'M19 14v4a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h4'],
  trash: ['M4 7h16', 'M9 7V4h6v3', 'M6 7l1 13h10l1-13'],
  info: ['M12 4a8 8 0 1 0 0 16a8 8 0 0 0 0-16z', 'M12 11v5', 'M12 8h.01'],
  video: [
    'M4 6h12a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1z',
    'M17 10l4-2v8l-4-2',
  ],
  stop: ['M6 6h12v12H6z'],
} as const

/** The name of an icon of the set. */
export type IconName = keyof typeof ICONS

/** Every icon of the set, in the order of the theme preview page. */
export const ICON_NAMES = Object.keys(ICONS) as IconName[]
