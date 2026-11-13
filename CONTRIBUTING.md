# Contributing to yt-mirror

Thank you for wanting to help. This project is built to be easy to work on for people and for AI agents, which means it has clear rules. Please follow them.

## Before you start

1. Read [AGENTS.md](AGENTS.md) (it is the short orientation for everyone, not only agents).
2. Read the parts of [docs/SPEC.md](docs/SPEC.md) that your change touches.
3. For anything larger than a small fix, open an issue first and describe what you want to do. Features that are not in the specification need agreement before code.

## Reporting a bug

Use "Report a problem" inside the app when you can: it prepares a debug report and opens the issue form. Otherwise open a bug report issue and fill in the template.

## Making a change

1. Fork and create a branch.
2. Follow [docs/CODING-STANDARDS.md](docs/CODING-STANDARDS.md), including the definition of done.
3. Add or update tests ([docs/TESTING.md](docs/TESTING.md)). Name the requirement IDs they cover.
4. Update the documentation and `CHANGELOG.md` when behaviour changes.
5. Make sure all checks pass locally, then open a pull request that says which requirement IDs it implements and how you tested it.

## Commit messages

`type(scope): summary`, for example `fix(naming): keep ID suffix when a title is shortened`. See the coding standards for the full convention.

## Conduct

Everyone taking part is expected to follow the [code of conduct](CODE_OF_CONDUCT.md).
