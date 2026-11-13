"""Tests of ``ytmirror.app.logging_setup``."""

import io
import json
import logging
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

import pytest
import structlog
from ulid import ULID

from tests.fixtures.fakes.clock import FakeClock
from ytmirror.app.logging_setup import (
    EXTERNAL_EVENT,
    REDACTED,
    LogWriter,
    SecretRedactor,
    configure_logging,
    new_run_id,
    remove_old_logs,
    set_verbose,
)

RUN_ID = "01JCD0TESTRUN0000000000000"

_open_writers: list[LogWriter] = []


@pytest.fixture(autouse=True)
def close_log_files() -> Iterator[None]:
    """Close every log file a test opened."""
    yield
    for writer in _open_writers:
        writer.close()
    _open_writers.clear()


class Pipeline:
    """A configured log pipeline writing into a temp folder."""

    def __init__(self, logs_dir: Path, clock: FakeClock, *, verbose: bool = False) -> None:
        """Configure logging the way the app does."""
        self.logs_dir = logs_dir
        self.console = io.StringIO()
        self.redactor = SecretRedactor()
        self.writer: LogWriter = configure_logging(
            logs_dir=logs_dir,
            verbose=verbose,
            clock=clock,
            run_id=RUN_ID,
            redactor=self.redactor,
            console=self.console,
        )
        _open_writers.append(self.writer)

    def lines(self, day: str = "2026-11-13") -> list[dict[str, object]]:
        """Return the parsed lines of one daily file."""
        path = self.logs_dir / f"yt-mirror-{day}.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def pipeline(tmp_path: Path, clock: FakeClock) -> Pipeline:
    """The pipeline at the Normal level."""
    return Pipeline(tmp_path / "logs", clock)


def test_a_line_has_all_required_fields_in_the_documented_order(pipeline: Pipeline) -> None:
    """R-LG-01: ts, level, event, component, msg and run_id are on every line."""
    log = structlog.get_logger("ytmirror.services.downloader")

    log.info("download.finished", msg="Download finished", height=1080)

    (line,) = pipeline.lines()
    assert list(line) == ["ts", "level", "event", "component", "msg", "run_id", "height"]
    assert line == {
        "ts": "2026-11-13T09:28:04.512Z",
        "level": "info",
        "event": "download.finished",
        "component": "services.downloader",
        "msg": "Download finished",
        "run_id": RUN_ID,
        "height": 1080,
    }


def test_each_line_is_one_compact_json_object(pipeline: Pipeline) -> None:
    """R-LG-01: one JSON object per line, in the compact form of docs/LOGGING.md section 1."""
    log = structlog.get_logger("ytmirror.app.main")

    log.info("app.started", msg="Started, with a comma", title="Caf\u00e9 \u2603")
    log.info("app.stopping", msg="Stopping")

    raw_lines = (
        (pipeline.logs_dir / "yt-mirror-2026-11-13.jsonl").read_text(encoding="utf-8").splitlines()
    )
    assert len(raw_lines) == 2
    assert raw_lines[0].startswith('{"ts":"2026-11-13T09:28:04.512Z","level":"info","event":')
    assert '"title":"Caf\u00e9 \u2603"' in raw_lines[0]


def test_the_timestamp_is_utc_whatever_zone_the_clock_reports(tmp_path: Path) -> None:
    """R-LG-01, R-DT-02: log times are UTC with millisecond precision."""
    tehran = timezone(timedelta(hours=3, minutes=30))
    clock = FakeClock(datetime(2026, 11, 14, 1, 15, 0, 7000, tzinfo=tehran))
    pipeline = Pipeline(tmp_path / "logs", clock)

    structlog.get_logger("ytmirror.app.main").info("app.started", msg="Started")

    (line,) = pipeline.lines("2026-11-13")
    assert line["ts"] == "2026-11-13T21:45:00.007Z"


def test_a_new_file_starts_each_utc_day(pipeline: Pipeline, clock: FakeClock) -> None:
    """R-LG-01: logs are rotated daily."""
    log = structlog.get_logger("ytmirror.app.main")

    log.info("app.started", msg="Before midnight")
    clock.set(datetime(2026, 11, 14, 0, 0, 1, tzinfo=UTC))
    log.info("app.stopping", msg="After midnight")

    assert [line["msg"] for line in pipeline.lines("2026-11-13")] == ["Before midnight"]
    assert [line["msg"] for line in pipeline.lines("2026-11-14")] == ["After midnight"]


def test_lines_are_appended_to_an_existing_daily_file(tmp_path: Path, clock: FakeClock) -> None:
    """R-LG-01: a second start on the same day keeps the earlier lines."""
    first = Pipeline(tmp_path / "logs", clock)
    structlog.get_logger("ytmirror.app.main").info("app.started", msg="First run")
    first.writer.close()

    second = Pipeline(tmp_path / "logs", clock)
    structlog.get_logger("ytmirror.app.main").info("app.started", msg="Second run")

    assert [line["msg"] for line in second.lines()] == ["First run", "Second run"]


def test_normal_detail_drops_debug_lines(pipeline: Pipeline) -> None:
    """R-LG-01: "Normal" writes info and above (docs/LOGGING.md section 1)."""
    log = structlog.get_logger("ytmirror.api.request_log")

    log.debug("api.request", msg="Request handled")
    log.info("app.started", msg="Started")

    assert [line["event"] for line in pipeline.lines()] == ["app.started"]


def test_verbose_detail_keeps_debug_lines(tmp_path: Path, clock: FakeClock) -> None:
    """R-LG-01: "Verbose" and ``--debug`` write debug and above."""
    pipeline = Pipeline(tmp_path / "logs", clock, verbose=True)

    structlog.get_logger("ytmirror.api.request_log").debug("api.request", msg="Request handled")

    assert [line["level"] for line in pipeline.lines()] == ["debug"]


def test_the_level_can_be_raised_while_running(pipeline: Pipeline) -> None:
    """R-LG-01: the "Log detail" setting is applied after the settings are loaded."""
    log = structlog.get_logger("ytmirror.api.request_log")

    set_verbose(True)
    log.debug("api.request", msg="Now visible")
    set_verbose(False)
    log.debug("api.request", msg="Hidden again")

    assert [line["msg"] for line in pipeline.lines()] == ["Now visible"]


def test_a_registered_secret_is_removed_wherever_it_appears(pipeline: Pipeline) -> None:
    """R-LG-01: the session token is never written (docs/LOGGING.md section 1, rule 4)."""
    pipeline.redactor.register("s3cr3t-token")
    log = structlog.get_logger("ytmirror.app.main")

    log.info(
        "app.started",
        msg="Open http://127.0.0.1:1/?token=s3cr3t-token",
        url="http://127.0.0.1:1/?token=s3cr3t-token",
        nested={"deep": ["x s3cr3t-token y"]},
    )

    text = (pipeline.logs_dir / "yt-mirror-2026-11-13.jsonl").read_text(encoding="utf-8")
    assert "s3cr3t-token" not in text
    assert "s3cr3t-token" not in pipeline.console.getvalue()
    (line,) = pipeline.lines()
    assert line["url"] == f"http://127.0.0.1:1/?token={REDACTED}"
    assert line["nested"] == {"deep": [f"x {REDACTED} y"]}


def test_fields_named_like_secrets_are_removed_even_when_unknown(pipeline: Pipeline) -> None:
    """R-LG-01, R-SE-03: an API key or token field is redacted by its name alone."""
    log = structlog.get_logger("ytmirror.app.main")

    log.info(
        "app.config",
        msg="Config",
        api_key="AIza-not-registered",
        headers={"Authorization": "Bearer abc", "Accept": "*/*"},
    )

    (line,) = pipeline.lines()
    assert line["api_key"] == REDACTED
    assert line["headers"] == {"Authorization": REDACTED, "Accept": "*/*"}


def test_an_empty_secret_is_not_registered(pipeline: Pipeline) -> None:
    """R-LG-01: registering nothing must not blank out every text."""
    pipeline.redactor.register("")

    structlog.get_logger("ytmirror.app.main").info("app.started", msg="Started")

    assert pipeline.lines()[0]["msg"] == "Started"


def test_an_exception_is_written_with_its_stack_trace(pipeline: Pipeline) -> None:
    """R-LG-01: exceptions are logged with ``exc_info`` (docs/LOGGING.md section 1, rule 6)."""
    log = structlog.get_logger("ytmirror.app.main")

    try:
        raise ValueError("boom")
    except ValueError:
        log.error("app.crashed", msg="Crashed", error_code="INTERNAL", exc_info=True)

    (line,) = pipeline.lines()
    assert line["error_code"] == "INTERNAL"
    assert "ValueError: boom" in str(line["exception"])
    assert "exc_info" not in line
    assert "ValueError: boom" in pipeline.console.getvalue()


def test_a_line_without_a_sentence_uses_its_event_name(pipeline: Pipeline) -> None:
    """R-LG-01: ``msg`` is present on every line, even when the caller forgot it."""
    structlog.get_logger("ytmirror.app.main").info("app.started")

    assert pipeline.lines()[0]["msg"] == "app.started"


def test_the_console_shows_one_readable_line_per_event(pipeline: Pipeline) -> None:
    """R-LG-01: the console shows the same events in a one-line form (rule 7)."""
    structlog.get_logger("ytmirror.app.main").info("app.started", msg="Started", version="1.0.0")

    assert pipeline.console.getvalue() == (
        "09:28:04.512 info    app.started  Started  version=1.0.0\n"
    )


def test_without_a_console_only_the_file_is_written(tmp_path: Path, clock: FakeClock) -> None:
    """R-LG-01: the file is the record. The console is optional."""
    writer = configure_logging(
        logs_dir=tmp_path / "logs",
        verbose=False,
        clock=clock,
        run_id=RUN_ID,
        redactor=SecretRedactor(),
        console=None,
    )

    structlog.get_logger("ytmirror.app.main").info("app.started", msg="Started")
    writer.close()

    assert (tmp_path / "logs" / "yt-mirror-2026-11-13.jsonl").read_text(encoding="utf-8")


def test_warnings_of_libraries_enter_the_same_file(pipeline: Pipeline) -> None:
    """R-LG-01: lines from uvicorn or Alembic are not lost and keep the line format."""
    logging.getLogger("uvicorn.error").warning("Something %s happened", "odd")

    (line,) = pipeline.lines()
    assert line["event"] == EXTERNAL_EVENT
    assert line["level"] == "warning"
    assert line["component"] == "uvicorn.error"
    assert line["msg"] == "Something odd happened"
    assert line["run_id"] == RUN_ID


def test_routine_lines_of_libraries_are_kept_only_in_verbose_detail(pipeline: Pipeline) -> None:
    """R-LG-01: library chatter appears only when the detail is Verbose."""
    library = logging.getLogger("alembic.runtime.migration")

    library.info("Hidden at Normal")
    set_verbose(True)
    library.info("Shown at Verbose")

    assert [line["msg"] for line in pipeline.lines()] == ["Shown at Verbose"]


def test_a_logger_without_a_name_reports_the_package_as_component(pipeline: Pipeline) -> None:
    """R-LG-01: ``component`` is never missing."""
    structlog.get_logger().info("app.started", msg="Started")

    assert pipeline.lines()[0]["component"] == "ytmirror"


def test_a_run_id_is_a_ulid_made_at_the_current_time(clock: FakeClock) -> None:
    """R-LG-01: every start gets a new ULID run ID that sorts by time."""
    run_id = new_run_id(clock)

    assert len(run_id) == 26
    assert ULID.from_str(run_id).datetime == clock.now()


def test_daily_files_older_than_fourteen_days_are_deleted(tmp_path: Path) -> None:
    """R-LG-01: logs are kept 14 days."""
    today = date(2026, 11, 20)
    names = {
        "old": "yt-mirror-2026-11-05.jsonl",
        "edge": "yt-mirror-2026-11-06.jsonl",
        "new": "yt-mirror-2026-11-20.jsonl",
    }
    for name in names.values():
        (tmp_path / name).write_text("{}\n", encoding="utf-8")

    removed = remove_old_logs(tmp_path, today)

    assert removed == [tmp_path / names["old"]]
    assert sorted(path.name for path in tmp_path.iterdir()) == [names["edge"], names["new"]]


def test_only_daily_log_files_are_ever_deleted(tmp_path: Path) -> None:
    """R-LG-01: cleanup never touches a file it does not own."""
    keep = ["notes.txt", "yt-mirror-not-a-date.jsonl", "install.log", "yt-mirror-2020-01-01.txt"]
    for name in keep:
        (tmp_path / name).write_text("x", encoding="utf-8")
    (tmp_path / "jobs").mkdir()

    removed = remove_old_logs(tmp_path, date(2026, 11, 20))

    assert removed == []
    assert sorted(path.name for path in tmp_path.iterdir()) == sorted([*keep, "jobs"])
