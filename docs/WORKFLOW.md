# yt-mirror: Working Process

How work moves from "next milestone" to "merged". This applies to every contributor, human or AI. The maintainer reviews and merges. Nobody else does.

## 1. Start of every session

1. Read `AGENTS.md`, then `docs/STATUS.md`.
2. Run `git status`, `git fetch`, and `gh pr list --state open`.
3. Decide what to do from this table. Do exactly one of these, then stop.

| Situation | What to do |
|---|---|
| A milestone is `In review` and its pull request is open with no new review comments | Do nothing on that milestone. Tell the maintainer it is waiting for review. Do not start the next milestone |
| A milestone is `In review` and its pull request has review comments or failing checks | Check out its branch, address every comment, push, reply on the pull request, and stop |
| A milestone is `In progress` (branch exists, no pull request) | Check out its branch and continue it |
| No milestone is `In progress` or `In review`, and the working tree is clean | Start the milestone named in "Next milestone to start" |
| Anything else (dirty tree on `main`, unknown branches, status that does not match git) | Stop and ask the maintainer |

Never work on two milestones at once. Never skip a milestone.

## 2. Doing a milestone

1. `git switch main && git pull`, then create the branch `m<N>-<short-name>`, for example `m3-download-one-video`.
2. First commit on the branch: set the milestone to `In progress` in `docs/STATUS.md` with the branch name.
3. Resolve the milestone's open questions first (`docs/OPEN-QUESTIONS.md`). Record the answers.
4. Implement requirement by requirement: tests and code together, small commits, all checks passing at every commit (`docs/CODING-STANDARDS.md`).
5. Push the branch early and often (`git push -u origin <branch>`), so the work is never only on one machine.
6. When the milestone's acceptance list in `docs/IMPLEMENTATION-PLAN.md` passes locally, do the self-review in section 4.

## 3. Opening the pull request

1. Last commit before the pull request: in `docs/STATUS.md` set the milestone to `In review`, set "Next milestone to start" to the following one, and add any notes for later sessions. Update `CHANGELOG.md`.
2. Open the pull request against `main` with `gh pr create`, using the repository's template. The title is `M<N>: <milestone title>`. The description lists:
   - the requirement IDs implemented,
   - how each acceptance item was verified,
   - what could not be verified and why,
   - open questions that were resolved, and any new ones,
   - anything the maintainer must test by hand.
3. Add the pull request number to `docs/STATUS.md` in a follow-up commit on the same branch.
4. Wait for the automated checks. If any fail, fix them before asking for review.
5. Tell the maintainer the pull request is ready, with its link. Then **stop**. Do not merge. Do not start the next milestone.

## 4. Self-review before asking for review

- Read the full diff once as a reviewer would.
- Every new behaviour has tests that name requirement IDs. Every test would fail if the behaviour broke.
- All commands in the "Commands" table of `AGENTS.md` that apply pass locally.
- Docs, glossary, log events and error codes are updated.
- No leftovers: debug output, commented-out code, unrelated changes.

## 5. Review and merge (maintainer)

1. The maintainer reviews on GitHub and either requests changes or approves.
2. Requested changes are made as new commits on the same branch (no force push, so the review stays readable).
3. The maintainer merges with a merge commit or a squash, their choice. The merge is the moment the milestone becomes `Done`.
4. After the merge, the next session's first commit on the new milestone branch sets the merged milestone to `Done` with the merge date.

## 6. Automated checks (GitHub Actions)

Set up in milestone M0 as `.github/workflows/ci.yml`.

- **Triggers:** every pull request (when opened and on every new commit pushed to it) and every push to `main`.
- **Runner:** macOS, because file date behaviour must be tested on the real file system.
- **Jobs:** lint and format check, type checks, layer rules, backend tests with coverage thresholds, frontend tests, build, end-to-end tests, requirement coverage script, generated API types are current, no em dashes in the repository.
- **Never in CI:** tests marked `live` (they need the real YouTube).
- A pull request is not ready for review while any check fails.

Recommended GitHub settings for `main` (the maintainer sets these once, in the repository settings): require a pull request before merging, require the CI checks to pass, and block force pushes. Because the maintainer's own account may be the one that opens the pull requests, do not require an approving review, or GitHub will not let the author merge.

## 7. Rules that always hold

- Never commit to `main` directly. Never merge. Never force push. Never rewrite history.
- Pushing is allowed only for the current milestone branch.
- No AI attribution in commits or pull requests (`AGENTS.md`).
- If the spec is wrong or unclear, stop and ask. Do not guess and do not change the spec without the maintainer.
- Small fixes outside a milestone follow the same path on a branch named `fix-<short-name>`, without changing the milestone table.
