# yt-mirror

Keep folders on your Mac in sync with YouTube channels.

> **Status: in development.** The app starts as a native Mac app, installs the tools it needs on first run, and shows a placeholder page. The features below are being built milestone by milestone. See [docs/STATUS.md](docs/STATUS.md).

## What it will do

- Add YouTube channels and see every video with thumbnail, title, length, date and status.
- Mirror selected videos, or turn on auto-mirror to download everything and keep up with new uploads.
- Exclude videos forever, by hand or with simple rules.
- Produce clean files: named exactly like the video title, dated with the YouTube publish time so Finder sorts a folder like the channel, with description, chapters, thumbnail and English subtitles embedded.
- Adopt videos you already downloaded and fix their names, dates and metadata without downloading again.
- Install with one line, install its own tools, update itself, and explain problems in plain language.

macOS 15 or newer, on Apple Silicon or Intel. Free and open source under the MIT license.

## Run it from a clone

For developers. The one-line installer for everyone else comes with the first release.

```
git clone https://github.com/mderis/yt-mirror.git
cd yt-mirror
./start
```

You need macOS 15 or newer and [Node.js](https://nodejs.org) 24 or newer (to build the interface). `./start` downloads everything else (uv, Python, the Python packages) into the `tools/` folder of the clone, and the app's first-run screen adds ffmpeg and Deno there. Nothing is installed system-wide. A clone appears in the Dock as "yt-mirror (dev)".

| Command | What it does |
|---|---|
| `./start` | Start the app in its window |
| `./start --dev` | The same with hot reload of the interface |
| `./start --browser` | Open in the default browser instead of the window |
| `./start --debug` | Verbose logs, and developer tools in the window |
| `./start --doctor` | Check the environment and report |

Commands for tests and checks are in [AGENTS.md](AGENTS.md).

Repository: https://github.com/mderis/yt-mirror
Website (after the first release): https://mderis.github.io/yt-mirror/

## Documentation

| Document | Content |
|---|---|
| [docs/SPEC.md](docs/SPEC.md) | What the app does, with requirement IDs |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How it is built |
| [docs/DESIGN.md](docs/DESIGN.md) | Designs for every screen ([open the mockups](docs/design/v1/index.html)) |
| [docs/STATUS.md](docs/STATUS.md) | Where the project stands right now |
| [docs/IMPLEMENTATION-PLAN.md](docs/IMPLEMENTATION-PLAN.md) | Build order, milestone by milestone |
| [docs/WORKFLOW.md](docs/WORKFLOW.md) | Branches, pull requests, review, automated checks |
| [docs/TESTING.md](docs/TESTING.md) | Test strategy |
| [docs/LOGGING.md](docs/LOGGING.md) | Logs, error codes, debugging |
| [docs/RELEASE-AND-UPDATE.md](docs/RELEASE-AND-UPDATE.md) | Installer, updater, releases, website |
| [docs/CODING-STANDARDS.md](docs/CODING-STANDARDS.md) | How code is written here |
| [docs/GLOSSARY.md](docs/GLOSSARY.md) | The project's vocabulary |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Why things are the way they are |
| [docs/OPEN-QUESTIONS.md](docs/OPEN-QUESTIONS.md) | Assumptions to verify and pending choices |
| [docs/ROADMAP.md](docs/ROADMAP.md) | What is out of scope for version 1 |
| [AGENTS.md](AGENTS.md) | Start here if you are an AI agent |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Please read the [code of conduct](CODE_OF_CONDUCT.md).

## Responsible use

Only download videos you have the right to keep. You are responsible for complying with YouTube's terms and the law where you live.

## License

[MIT](LICENSE)
