"""The debug log pipeline (docs/LOGGING.md section 1). Implements R-LG-01.

Every log line is one JSON object in ``data/logs/yt-mirror-YYYY-MM-DD.jsonl``
(a new file each UTC day) and one readable line on the console. Modules log
with ``structlog.get_logger(__name__)`` and an event name from the catalogue:

    _log.info("app.started", msg="yt-mirror started", version="1.0.0")

This module must not decide what gets logged. It only shapes and writes.

Tests: backend/tests/unit/app/test_logging_setup.py
"""

import json
import logging
import threading
from collections.abc import Mapping, MutableMapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TextIO, cast

import structlog
from structlog.typing import FilteringBoundLogger, Processor
from ulid import ULID

from ytmirror.ports.clock import Clock

REDACTED = "[redacted]"
EXTERNAL_EVENT = "app.external_log"
KEEP_DAYS = 14

_FILE_PREFIX = "yt-mirror-"
_FILE_SUFFIX = ".jsonl"
_PACKAGE_PREFIX = "ytmirror."
_LEAD_FIELDS = ("ts", "level", "event", "component", "msg", "run_id")
_SECRET_KEYS = frozenset(
    {"token", "session_token", "api_key", "authorization", "cookie", "set-cookie", "password"}
)

type EventDict = MutableMapping[str, object]


class SecretRedactor:
    """Removes secrets from every log line (docs/LOGGING.md section 1, rule 4).

    A field whose name says it is a secret is replaced as a whole. A known
    secret value is replaced wherever it appears inside any text.
    """

    def __init__(self) -> None:
        """Create a redactor that knows no secret values yet."""
        self._secrets: set[str] = set()

    def register(self, secret: str) -> None:
        """Make a secret value known, so it is removed from all later lines.

        Args:
            secret: The value to hide, for example the session token.
        """
        if secret:
            self._secrets.add(secret)

    def __call__(self, _logger: object, _method: str, event: EventDict) -> EventDict:
        """Redact one log line. This is a structlog processor."""
        for key in list(event):
            event[key] = REDACTED if key.lower() in _SECRET_KEYS else self._clean(event[key])
        return event

    def _clean(self, value: object) -> object:
        if isinstance(value, str):
            for secret in self._secrets:
                value = value.replace(secret, REDACTED)
            return value
        if isinstance(value, Mapping):
            mapping = cast(Mapping[object, object], value)
            return {
                key: REDACTED if str(key).lower() in _SECRET_KEYS else self._clean(item)
                for key, item in mapping.items()
            }
        if isinstance(value, (list, tuple)):
            return [self._clean(item) for item in cast(Sequence[object], value)]
        return value


class LogWriter:
    """Writes finished log lines to the daily file and to the console."""

    def __init__(self, logs_dir: Path, console: TextIO | None) -> None:
        """Create the writer.

        Args:
            logs_dir: The folder for the daily files. It must exist.
            console: Where the readable lines go, or None for no console output.
        """
        self._logs_dir = logs_dir
        self._console = console
        self._lock = threading.Lock()
        self._day = ""
        self._file: TextIO | None = None

    def write(self, record: dict[str, object]) -> None:
        """Write one log line.

        Args:
            record: The finished line. Its ``ts`` field decides the daily file.
        """
        line = json.dumps(record, ensure_ascii=False, default=str, separators=(",", ":"))
        day = str(record["ts"])[:10]
        with self._lock:
            if day != self._day or self._file is None:
                self._close_file()
                path = self._logs_dir / f"{_FILE_PREFIX}{day}{_FILE_SUFFIX}"
                self._file = path.open("a", encoding="utf-8")
                self._day = day
            self._file.write(line + "\n")
            self._file.flush()
            if self._console is not None:
                self._console.write(_console_line(record) + "\n")

    def close(self) -> None:
        """Close the current daily file."""
        with self._lock:
            self._close_file()

    def _close_file(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None


class _SinkLogger:
    """The last step of the pipeline: adds the component and hands the line to the writer."""

    def __init__(self, name: str, writer: LogWriter) -> None:
        self._component = name.removeprefix(_PACKAGE_PREFIX)
        self._writer = writer

    def msg(self, **event: object) -> None:
        event["component"] = self._component
        record = {key: event[key] for key in _LEAD_FIELDS if key in event}
        record.update({key: value for key, value in event.items() if key not in record})
        self._writer.write(record)

    debug = info = warning = error = critical = msg


class _BridgeHandler(logging.Handler):
    """Sends lines of libraries that use the standard logging module into the pipeline."""

    def emit(self, record: logging.LogRecord) -> None:
        logger: FilteringBoundLogger = structlog.get_logger(record.name)
        logger.log(record.levelno, EXTERNAL_EVENT, msg=record.getMessage())


def new_run_id(clock: Clock) -> str:
    """Return a new run ID: a ULID made at the current time.

    Args:
        clock: The source of the current time.
    """
    return str(ULID.from_datetime(clock.now()))


def configure_logging(
    *,
    logs_dir: Path,
    verbose: bool,
    clock: Clock,
    run_id: str,
    redactor: SecretRedactor,
    console: TextIO | None,
) -> LogWriter:
    """Set up the log pipeline for this run.

    Args:
        logs_dir: The folder for the daily files. Created when missing.
        verbose: True writes ``debug`` and above, False writes ``info`` and above.
        clock: The source of the ``ts`` field.
        run_id: The ID of this run, added to every line.
        redactor: Removes secrets from every line.
        console: Where the readable lines go, or None for no console output.

    Returns:
        The writer. Close it when the app stops.
    """
    logs_dir.mkdir(parents=True, exist_ok=True)
    writer = LogWriter(logs_dir, console)

    def add_fixed_fields(_logger: object, _method: str, event: EventDict) -> EventDict:
        event["ts"] = _timestamp(clock.now())
        event["run_id"] = run_id
        event.setdefault("msg", event.get("event", ""))
        return event

    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        add_fixed_fields,
        structlog.processors.ExceptionRenderer(),
        redactor,
    ]
    structlog.configure(
        processors=processors,
        logger_factory=lambda *names: _SinkLogger(names[0] if names else "ytmirror", writer),
        cache_logger_on_first_use=False,
    )
    set_verbose(verbose)
    logging.getLogger().handlers = [_BridgeHandler()]
    return writer


def set_verbose(verbose: bool) -> None:
    """Change the level of the running pipeline (the "Log detail" setting).

    Args:
        verbose: True writes ``debug`` and above, False writes ``info`` and above.
    """
    level = logging.DEBUG if verbose else logging.INFO
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(level))
    logging.getLogger().setLevel(logging.INFO if verbose else logging.WARNING)


def remove_old_logs(logs_dir: Path, today: date) -> list[Path]:
    """Delete daily log files older than 14 days (R-LG-01).

    Only files that follow the daily naming pattern are touched.

    Args:
        logs_dir: The folder with the daily files.
        today: The current UTC date.

    Returns:
        The files that were deleted.
    """
    oldest_kept = today - timedelta(days=KEEP_DAYS)
    removed: list[Path] = []
    for path in sorted(logs_dir.glob(f"{_FILE_PREFIX}*{_FILE_SUFFIX}")):
        day_text = path.name.removeprefix(_FILE_PREFIX).removesuffix(_FILE_SUFFIX)
        try:
            day = date.fromisoformat(day_text)
        except ValueError:
            continue
        if day < oldest_kept:
            path.unlink()
            removed.append(path)
    return removed


def _timestamp(moment: datetime) -> str:
    """Return a moment as UTC text with millisecond precision, ending in ``Z``."""
    utc = moment.astimezone(UTC)
    return f"{utc:%Y-%m-%dT%H:%M:%S}.{utc.microsecond // 1000:03d}Z"


def _console_line(record: dict[str, object]) -> str:
    """Return the readable one-line form of a log line."""
    clock_time = str(record["ts"])[11:23]
    extras = " ".join(
        f"{key}={value}"
        for key, value in record.items()
        if key not in _LEAD_FIELDS and key != "exception"
    )
    line = f"{clock_time} {record['level']!s:<7} {record['event']}  {record['msg']}"
    if extras:
        line += f"  {extras}"
    if "exception" in record:
        line += f"\n{record['exception']}"
    return line
