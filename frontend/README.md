# frontend

The interface of yt-mirror: a Vue 3 single-page app in TypeScript, built with Vite and styled with Tailwind on top of the theme center.

| Folder | Content |
|---|---|
| `src/design/` | **The theme center**: every visual value. Read its README before touching anything visual |
| `src/i18n/` | Every user-visible text. Components contain no text |
| `src/api/` | The generated API types (`schema.d.ts`) and the thin typed client. The only place that calls `fetch` |
| `src/stores/` | Pinia stores. Server data lives here |
| `src/features/` | One folder per feature. Feature components talk to stores |
| `src/components/` | Shared presentational components (from milestone M2). Each one is also added to the theme preview page |
| `tools/` | Developer tools: the theme lint and the API type generator |
| `tests/` | Vitest tests. Every test title starts with the requirement IDs it covers |

## Commands

Run from the repository root.

| Task | Command |
|---|---|
| Tests with coverage | `npm --prefix frontend test` |
| ESLint, theme lint, Prettier | `npm --prefix frontend run lint` |
| Theme lint alone | `npm --prefix frontend run lint:theme` |
| Types | `npm --prefix frontend run typecheck` |
| Build into `frontend/dist` | `npm --prefix frontend run build` |
| Regenerate the API types | `npm --prefix frontend run gen:api` |
| Format | `npm --prefix frontend run format` |

`./start --dev` runs the app with hot reload. The theme preview page is then at http://127.0.0.1:5173/theme-preview.html.

## Rules (docs/CODING-STANDARDS.md section 4)

- Outside `src/design/` only token-based utility classes are allowed. No raw colours, font names, sizes or Tailwind arbitrary values. The theme lint fails otherwise.
- No text in templates. Add a key to `src/i18n/en.ts`.
- Components do not call `fetch`. Stores use the API client.
- A link that leaves the app is an anchor with `target="_blank"` (docs/ARCHITECTURE.md section 7.8).
