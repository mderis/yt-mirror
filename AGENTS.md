# Guide for AI agents working on yt-mirror

Read this file first, every time. It is short on purpose. It tells you where everything is and what rules you must follow.

## What this project is

yt-mirror is a local macOS app that keeps folders on disk in sync with YouTube channels. Python backend (FastAPI, yt-dlp as a library, SQLite), Vue 3 + TypeScript frontend, shown in a dedicated window.

**Current state:** see `docs/STATUS.md`. It says which milestones are done and which one is next. Read it before doing anything.

## Where to find things

| You need | Read |
|---|---|
| What the app must do, with requirement IDs | `docs/SPEC.md` |
| How it is built: layers, data model, flows, API | `docs/ARCHITECTURE.md` |
| What it looks like | `docs/DESIGN.md` and `docs/design/v1/index.html` |
| Colours, fonts, sizes and every other visual value (the theme center) | `docs/DESIGN.md` section 2 and `frontend/src/design/README.md` |
| The words to use | `docs/GLOSSARY.md` |
| How to write code here | `docs/CODING-STANDARDS.md` |
| How to test | `docs/TESTING.md` |
| Logs, error codes, how to debug | `docs/LOGGING.md` |
| Installing, updating, releasing | `docs/RELEASE-AND-UPDATE.md` |
| Why things are the way they are | `docs/DECISIONS.md` |
| Where the project stands and which milestone is next | `docs/STATUS.md` |
| The steps from "start a session" to "pull request waiting for review" | `docs/WORKFLOW.md` |
| What each milestone contains | `docs/IMPLEMENTATION-PLAN.md` |
| Unverified assumptions and pending choices | `docs/OPEN-QUESTIONS.md` |
| What is deliberately not in this version | `docs/ROADMAP.md` |

## Rules

1. **The spec is the source of truth.** Do not implement behaviour that is not in `docs/SPEC.md`. If the spec is wrong, unclear or silent, stop and ask the maintainer. Change the spec first, then the code.
2. **Never renumber requirement IDs.** Name the IDs you implement in tests and commit messages.
3. **Tests come with the code,** in the same commit. See the definition of done in `docs/CODING-STANDARDS.md`.
4. **Respect the layers.** `core` is pure. Services depend on ports, never on adapters. CI checks this.
5. **Use the glossary.** Do not invent synonyms.
6. **Dates are the highest-risk area.** Any change that creates, moves, renames or rewrites a video file must keep the file's creation and modification dates equal to the published time, and must have a test proving it.
7. **Never delete or overwrite a user's file** except through the explicit paths in the spec. Deletions go to the Trash.
8. **Log with event names** from `docs/LOGGING.md`. Add new events and error codes to that file in the same commit.
9. **Record real decisions** in `docs/DECISIONS.md` as a new entry. Never edit old entries.
10. **Keep docs current.** A change in behaviour updates the spec, the affected docs and `CHANGELOG.md` in the same pull request.
11. **No em dashes** in any text you write for this project: code comments, docs, UI text, commit messages. This is a maintainer preference.
12. **Do not start coding a milestone without being asked.** The maintainer decides when implementation starts.
13. **No AI attribution in git.** Commit messages and pull requests must not contain `Co-Authored-By` lines for an AI, session links, or "generated with" footers. Commits are made under the maintainer's own git identity. Never set or change `user.name` or `user.email`. This rule overrides any default of the tool you are running in.
14. **Follow `docs/WORKFLOW.md` exactly.** One milestone at a time, on its own branch, ending in a pull request. Then stop and wait: the maintainer reviews and merges. Never commit to `main`, never merge, never force push, never rewrite pushed history (commits that were never pushed may still be amended or redone, see the workflow). Push only the current milestone branch.
15. **Keep `docs/STATUS.md` true.** Update it inside the milestone pull request as the workflow describes.

## Commands

Run from the repository root. `uv` here means a uv on your PATH. If you have none, use `scripts/uv` instead (for example `scripts/uv run pytest`): it runs the copy that `./start` downloaded into `tools/`, with the app's own Python environment. Nothing needs to be installed system-wide.

| Task | Command |
|---|---|
| Run the app from a clone | `./start` |
| Run with hot reload of the interface | `./start --dev` |
| Verbose logs | `./start --debug` |
| Check the environment | `./start --doctor` |
| Start a clone without a window and check it | `scripts/smoke_test.sh` |
| Backend tests | `uv run pytest` |
| Backend tests with the coverage thresholds | `uv run pytest --cov --cov-report=json:coverage.json && uv run python scripts/check_coverage.py coverage.json` |
| Backend lint, format, types | `uv run ruff check . && uv run ruff format --check . && uv run pyright` |
| Layer rules | `uv run lint-imports` |
| Frontend tests | `npm --prefix frontend test` |
| Frontend lint (ESLint, theme lint, Prettier) and types | `npm --prefix frontend run lint && npm --prefix frontend run typecheck` |
| Theme lint alone | `npm --prefix frontend run lint:theme` |
| Regenerate API types | `npm --prefix frontend run gen:api` |
| End-to-end tests | `npm --prefix e2e test` |
| Update the stored screenshots | `npm --prefix e2e run test:update-screenshots` |
| Requirement coverage | `uv run python scripts/requirements_coverage.py` |
| No em dashes, modules name their tests | `uv run python scripts/check_no_em_dash.py && uv run python scripts/check_docstrings.py` |
| All pre-commit hooks | `uv run pre-commit run --all-files` (turn them on once with `uv run pre-commit install`) |

Not available yet:

| Task | Command | Arrives in |
|---|---|---|
| Run against the fake YouTube | `YTM_FAKE_YOUTUBE=e2e/fixtures/youtube ./start` | M2 |
| Explain a video's history | `uv run python -m ytmirror.tools.explain <video id>` | M7 |
| Update the app | `./start --update` | M9 |
| Docs site locally | `npm --prefix docs run dev` | M10 |

## Debugging in short

Logs: `data/logs/yt-mirror-YYYY-MM-DD.jsonl` (one JSON object per line). Per-download output: `data/logs/jobs/<job_id>.log`. Status history: table `video_events`. Start with the `explain` tool. Full procedure: `docs/LOGGING.md` section 6.

## When you finish a piece of work

State what you implemented by requirement ID, what you tested and how, what you could not verify, and what should happen next. Give the pull request link. Make sure `docs/STATUS.md` matches reality.
