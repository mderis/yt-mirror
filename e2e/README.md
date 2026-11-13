# e2e

End-to-end tests (docs/TESTING.md section 6): the real backend, started by the real `./start` without a window, and the real built interface, driven through WebKit and Chromium with Playwright.

```
npm --prefix e2e ci
npx --prefix e2e playwright install webkit chromium
npm --prefix e2e test
```

- The tests start two servers themselves: the app on port 47801 with a fresh data folder (`e2e/.data`), and the frontend development server on port 5174 for the theme preview page.
- **Screenshots** are in `tests/__screenshots__/`, one per browser. After an intended visual change run `npm --prefix e2e run test:update-screenshots`, look at the new images, and commit them.
- **Chromium cannot be downloaded everywhere.** Where Playwright's download is refused, use an installed Google Chrome: `YTM_E2E_CHROME_CHANNEL=chrome npm --prefix e2e test`.
- The fake YouTube (`e2e/fixtures/youtube/`) arrives in milestone M2.

Every test title starts with the requirement IDs it covers.
