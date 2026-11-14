# e2e

End-to-end tests (docs/TESTING.md section 6): the real backend, started by the real `./start` without a window, and the real built interface, driven through WebKit and Chromium with Playwright.

```
npm --prefix e2e ci
npx --prefix e2e playwright install webkit chromium
npm --prefix e2e test
```

- The tests start three servers themselves: the app on port 47801 with fresh folders in `e2e/.data`, the frontend development server on port 5174 for the theme preview page, and a small server on port 5175 that serves stand-ins for the tools the app downloads.
- **The tools are stand-ins.** The real ffmpeg and Deno are 30 MB each and come from the internet. `fixtures/tools/tools.mjs` packs tiny shell scripts like the real downloads and writes a manifest for them. The app is pointed at it with `YTM_TOOL_MANIFEST` and installs into a folder of its own (`YTM_TOOL_DIR`), never into the real `tools/`.
- **The first run has apps of its own.** The shared app is brought past its first run before the tests (`global-setup.ts`). A test of the first run itself starts its own app on empty folders (`tests/fresh-app.ts`) and can make a download fail for that app only.
- **Screenshots** are in `tests/__screenshots__/`, one per browser. After an intended visual change run `npm --prefix e2e run test:update-screenshots`, look at the new images, and commit them.
- **Chromium cannot be downloaded everywhere.** Where Playwright's download is refused, use an installed Google Chrome: `YTM_E2E_CHROME_CHANNEL=chrome npm --prefix e2e test`.
- **YouTube is a fake.** Every app the tests start gets `YTM_FAKE_YOUTUBE=fixtures/youtube`, a recorded world of channels (docs/TESTING.md section 4), and a library folder of its own (`YTM_LIBRARY_DIR`). No test asks the real YouTube or writes into `~/Movies/YouTube`.
- **Channels have apps of their own too.** A test that adds or changes channels starts its own app (`tests/fresh-app.ts`) and brings it past the first run through the API (`finishSetup`). The shared app never gets a channel.
- **The time zone is fixed** to UTC in `playwright.config.ts`, because dates are shown in the time zone of the machine (R-DT-02).

Every test title starts with the requirement IDs it covers.
