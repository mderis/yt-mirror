# yt-mirror: Coding Standards

The code is read far more often than it is written, by people and by AI agents who have no memory of earlier work. Optimise for a reader who opens one file cold.

CI enforces everything marked (CI). The rest is checked in review.

## 1. General

1. **Clarity over cleverness.** Prefer the obvious solution. If something is subtle, a comment says why.
2. **One name per concept.** Use the terms in [GLOSSARY.md](GLOSSARY.md) in code, UI text, logs and docs. A video is `synced`, never `downloaded` in one place and `mirrored` in another.
3. **Small units.** A function does one thing. Guideline: under 40 lines, at most 4 parameters, at most 3 levels of nesting. A file has one purpose. Guideline: under 400 lines.
4. **No dead code, no commented-out code, no TODO without an issue number.**
5. **Fail loudly in development, safely in production.** Programming errors raise. Expected failures are returned as typed errors with an error code.
6. **No hidden global state.** Dependencies are passed in. The container in `app/container.py` wires them.
7. **Every decision that is not obvious from the code is recorded** in [DECISIONS.md](DECISIONS.md).

## 2. Documentation in code

1. Every module starts with a docstring: what it is for, what it must not do, and where its counterpart tests live. (CI)
2. Every public class, function and method has a docstring: purpose, arguments, return value, errors, and the requirement IDs it implements where that applies. (CI, Ruff pydocstyle with the Google convention)
3. Comments explain **why**, never what. A comment that repeats the code is deleted.
4. Each package has a short `README.md` saying what belongs in it and what does not.
5. Example:

```python
def file_name_for(title: str, video_id: str, taken: Collection[str]) -> str:
    """Return the file name for a video, without a directory.

    Implements R-FN-01 to R-FN-05. The result is valid on macOS, at most
    255 bytes in UTF-8, and in Unicode NFC.

    Args:
        title: The video title exactly as YouTube reports it.
        video_id: The YouTube video ID, used only when a suffix is needed.
        taken: File names that already exist in the channel folder,
            compared case-insensitively.

    Returns:
        The file name including the ``.mkv`` extension.
    """
```

## 3. Python

- Python 3.12+. Full type hints everywhere. Pyright in strict mode passes with no ignores without a comment explaining each one. (CI)
- Ruff for linting and formatting, configuration in `pyproject.toml`. (CI)
- Domain data are frozen dataclasses or Pydantic models. No bare dicts or tuples across function boundaries.
- Enums for every closed set (statuses, error codes, job kinds). No string literals for these outside the enum.
- Time comes from the Clock port. Never call `time.time()` or `datetime.now()` in `core` or `services`. (CI, custom lint rule)
- Paths are `pathlib.Path`. Never build paths by string concatenation.
- Database access only inside `adapters/db`. Services receive repositories.
- No `print`. Use the logger with an event name from [LOGGING.md](LOGGING.md). (CI)
- Exceptions: catch the narrowest type. Never `except Exception: pass`. A broad catch is allowed only at a task boundary, where it logs and maps to `INTERNAL`.
- Layer rules from [ARCHITECTURE.md](ARCHITECTURE.md) section 4 are checked by import-linter. (CI)

## 4. TypeScript and Vue

- TypeScript strict mode. No `any` without a comment explaining it. (CI)
- Single-file components with `<script setup lang="ts">`. Props and emits are typed.
- Components are either presentational (props in, events out, no store access) or feature components (talk to stores). Shared components in `components/` are always presentational.
- Server data lives in Pinia stores, updated from API responses and SSE events. Components do not call `fetch`.
- API types are generated from the OpenAPI schema. Never write them by hand. (CI checks they are current)
- All user-visible text comes from `src/i18n/`. No string literals in templates. (CI)
- Styling uses Tailwind classes built on the design tokens. No raw hex colours in components. (CI)
- Every interactive element is a real `button`, `a`, or form control with an accessible name.
- ESLint, Prettier and `vue-tsc` pass. (CI)

## 5. Tests

- Test names read as sentences: `test_second_video_with_same_title_gets_id_suffix`.
- Arrange, act, assert, with blank lines between. One behaviour per test.
- Each test docstring starts with the requirement IDs it covers.
- Use builders (`make_video(status=...)`) for test data. No large inline fixtures.
- See [TESTING.md](TESTING.md) for the rest.

## 6. Git

- Small commits, one logical change each. The tree passes all checks at every commit.
- Message format (Conventional Commits): `type(scope): summary` in the imperative, at most 72 characters. Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `build`, `ci`. The body says why and names requirement IDs, for example `Implements R-FN-05`.
- Work happens on branches and reaches `main` through pull requests that pass CI.
- A change in behaviour updates the spec, the tests and the changelog in the same pull request.
- Pre-commit hooks run formatters, linters and fast tests.

## 7. Definition of done

A change is done when all of these are true:

- [ ] It implements the requirement IDs named in the pull request, and nothing else.
- [ ] Tests exist at the right layers, name the IDs, and pass.
- [ ] All CI checks pass, including coverage thresholds.
- [ ] Public code is documented. New events and error codes are in [LOGGING.md](LOGGING.md).
- [ ] User-visible changes match the designs, or the designs were updated.
- [ ] `CHANGELOG.md` has an entry under "Unreleased".
- [ ] Docs that describe the changed behaviour are updated.
- [ ] A reviewer who did not write it has approved it.
