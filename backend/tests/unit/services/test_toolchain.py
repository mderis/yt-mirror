"""Tests of ``ytmirror.services.toolchain``, against the fakes of its ports."""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field

import pytest
from structlog.testing import capture_logs

from tests.fixtures.fakes.app_meta_repository import InMemoryAppMetaRepository
from tests.fixtures.fakes.clock import FakeClock
from tests.fixtures.fakes.system_probe import FakeSystemProbe
from tests.fixtures.fakes.tool_box import FakeToolBox, fake_archive
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.models import (
    AppEvent,
    ArchiveKind,
    InstalledTool,
    ToolFile,
    ToolName,
    ToolReport,
    ToolSource,
    ToolSpec,
    ToolStatus,
    ToolUpdated,
)
from ytmirror.services.events import EventBus
from ytmirror.services.toolchain import SETUP_COMPLETED_KEY, ToolchainService

FIRST = "https://first.example"
SECOND = "https://second.example"
DENO_URL = "https://deno.example/deno.zip"


def archive(kind: ArchiveKind, programs: dict[str, str]) -> tuple[bytes, str]:
    """Return a pretend archive and its checksum."""
    content = fake_archive(kind, programs)
    return content, hashlib.sha256(content).hexdigest()


FFMPEG_ZIP, FFMPEG_SHA = archive(ArchiveKind.ZIP, {"ffmpeg": "ffmpeg version 9.0.2"})
FFPROBE_ZIP, FFPROBE_SHA = archive(ArchiveKind.ZIP, {"ffprobe": "ffprobe version 9.0.2"})
BOTH_TAR, BOTH_SHA = archive(
    ArchiveKind.TAR_XZ, {"ffmpeg": "ffmpeg version 8.1.3-Jellyfin", "ffprobe": "ffprobe 8.1.3"}
)
DENO_ZIP, DENO_SHA = archive(ArchiveKind.ZIP, {"deno": "deno 2.9.8"})


def specs() -> tuple[ToolSpec, ...]:
    """Return a manifest like the real one: ffmpeg with two sources, Deno with one."""
    first = (
        ToolFile(f"{FIRST}/ffmpeg.zip", FFMPEG_SHA, ArchiveKind.ZIP, ("ffmpeg",)),
        ToolFile(f"{FIRST}/ffprobe.zip", FFPROBE_SHA, ArchiveKind.ZIP, ("ffprobe",)),
    )
    second = (
        ToolFile(f"{SECOND}/both.tar.xz", BOTH_SHA, ArchiveKind.TAR_XZ, ("ffmpeg", "ffprobe")),
    )
    deno = (ToolFile(DENO_URL, DENO_SHA, ArchiveKind.ZIP, ("deno",)),)
    return (
        ToolSpec(
            ToolName.FFMPEG,
            ("ffmpeg", "ffprobe"),
            ("-version",),
            (
                ToolSource("martin-riedl", "9.0.2", {"arm64": first, "x86_64": first}),
                ToolSource("jellyfin-ffmpeg", "8.1.3-2", {"arm64": second, "x86_64": second}),
            ),
        ),
        ToolSpec(
            ToolName.DENO,
            ("deno",),
            ("--version",),
            (ToolSource("deno", "2.9.8", {"arm64": deno}),),
        ),
    )


@dataclass
class Setup:
    """A toolchain service with its fakes, and what it published."""

    tool_box: FakeToolBox = field(default_factory=FakeToolBox)
    probe: FakeSystemProbe = field(
        default_factory=lambda: FakeSystemProbe(packages={"yt-dlp": "2026.10.26"})
    )
    meta: InMemoryAppMetaRepository = field(default_factory=InMemoryAppMetaRepository)
    clock: FakeClock = field(default_factory=FakeClock)
    events: list[AppEvent | None] = field(default_factory=list[AppEvent | None])
    background: list[Callable[[], None]] = field(default_factory=list[Callable[[], None]])
    only_source: str | None = None

    def __post_init__(self) -> None:
        """Wire the service and offer every download of the manifest."""
        self.tool_box.downloads.update(
            {
                f"{FIRST}/ffmpeg.zip": FFMPEG_ZIP,
                f"{FIRST}/ffprobe.zip": FFPROBE_ZIP,
                f"{SECOND}/both.tar.xz": BOTH_TAR,
                DENO_URL: DENO_ZIP,
            }
        )
        bus = EventBus()
        bus.subscribe(self.events.append)
        self.service = ToolchainService(
            specs=specs(),
            tool_box=self.tool_box,
            probe=self.probe,
            meta=self.meta,
            events=bus,
            clock=self.clock,
            run_in_background=self.background.append,
            only_source=self.only_source,
        )

    def install(self, tool: ToolName) -> ToolReport:
        """Start an installation, run it to its end, and return the final state."""
        self.service.start_install(tool)
        self.finish_background_work()
        return self.report(tool)

    def finish_background_work(self) -> None:
        """Run what the service handed to the background."""
        waiting, self.background[:] = list(self.background), []
        for work in waiting:
            work()

    def report(self, tool: ToolName) -> ToolReport:
        """Return the current state of one tool."""
        return next(report for report in self.service.reports() if report.name is tool)

    def published(self, tool: ToolName) -> list[ToolReport]:
        """Return every state of a tool that was published, in order."""
        return [
            event.report
            for event in self.events
            if isinstance(event, ToolUpdated) and event.report.name is tool
        ]


def test_a_first_start_finds_python_and_ytdlp_and_misses_the_downloaded_tools() -> None:
    """R-IN-03: on first start the app shows which tools it needs."""
    setup = Setup()

    reports = setup.service.verify()

    assert [(report.name, report.status) for report in reports] == [
        (ToolName.PYTHON, ToolStatus.OK),
        (ToolName.YTDLP, ToolStatus.OK),
        (ToolName.FFMPEG, ToolStatus.MISSING),
        (ToolName.DENO, ToolStatus.MISSING),
    ]
    assert reports[0].version == "3.14.10"
    assert reports[1].version == "2026.10.26"
    assert [report.installable for report in reports] == [False, False, True, True]
    assert setup.service.setup_required() is True
    assert setup.tool_box.fetched == []


def test_a_missing_ytdlp_is_reported_and_cannot_be_installed_from_inside_the_app() -> None:
    """R-IN-04: a missing tool is shown as missing, never as a crash."""
    setup = Setup(probe=FakeSystemProbe())
    setup.service.verify()

    assert setup.report(ToolName.YTDLP) == ToolReport(ToolName.YTDLP, ToolStatus.MISSING)
    with pytest.raises(AppError) as refusal:
        setup.service.start_install(ToolName.YTDLP)
    assert refusal.value.code is ErrorCode.INVALID_REQUEST
    assert refusal.value.details == {"tool": "ytdlp"}


def test_a_tool_is_downloaded_checked_and_put_in_place() -> None:
    """R-IN-03: a missing tool is downloaded into the app folder and its checksum verified."""
    setup = Setup()
    setup.service.verify()

    final = setup.install(ToolName.FFMPEG)

    assert final == ToolReport(
        ToolName.FFMPEG, ToolStatus.OK, version="9.0.2", source="martin-riedl", installable=True
    )
    assert setup.tool_box.fetched == [f"{FIRST}/ffmpeg.zip", f"{FIRST}/ffprobe.zip"]
    assert setup.tool_box.installed(ToolName.FFMPEG) == InstalledTool("martin-riedl", "9.0.2")
    assert setup.tool_box.staging_is_empty(ToolName.FFMPEG)


def test_the_interface_sees_the_installation_start_progress_and_end() -> None:
    """R-IN-03: the download has visible progress, from start to the installed tool."""
    setup = Setup()
    setup.service.verify()

    started = setup.service.start_install(ToolName.FFMPEG)
    setup.finish_background_work()

    states = setup.published(ToolName.FFMPEG)
    progress = [state.progress for state in states if state.status is ToolStatus.INSTALLING]
    assert started == ToolReport(
        ToolName.FFMPEG, ToolStatus.INSTALLING, progress=0.0, installable=True
    )
    assert states[0] == started
    assert states[-1].status is ToolStatus.OK
    assert progress == sorted(p for p in progress if p is not None)
    assert progress[0] == 0.0
    known = [share for share in progress if share is not None]
    assert any(0.0 < share < 0.5 for share in known), "the first of two files shows progress"
    assert 0.5 in known
    assert any(0.5 < share < 1.0 for share in known), "the second file continues from the half"
    assert known[-1] == 1.0


def test_a_tool_that_is_being_installed_is_not_started_twice() -> None:
    """R-IN-03: a second click on the button does not start a second download."""
    setup = Setup()
    setup.service.verify()

    first = setup.service.start_install(ToolName.DENO)
    second = setup.service.start_install(ToolName.DENO)

    assert first == second
    assert len(setup.background) == 1


def test_a_file_that_does_not_match_its_checksum_is_never_installed() -> None:
    """R-IN-03: a download is verified against its checksum, and the second source is tried."""
    setup = Setup()
    setup.tool_box.downloads[f"{FIRST}/ffprobe.zip"] = b"tampered"
    setup.service.verify()

    with capture_logs() as logs:
        final = setup.install(ToolName.FFMPEG)

    failed = next(line for line in logs if line["event"] == "tool.install.failed")
    assert final.status is ToolStatus.OK
    assert final.source == "jellyfin-ffmpeg"
    assert final.version == "8.1.3-2"
    assert failed["source"] == "martin-riedl"
    assert failed["error_code"] == "CHECKSUM_MISMATCH"
    assert failed["expected"] == FFPROBE_SHA
    assert failed["actual"] == hashlib.sha256(b"tampered").hexdigest()
    assert setup.tool_box.run(ToolName.FFMPEG, "ffmpeg", []) == "ffmpeg version 8.1.3-Jellyfin"


def test_when_the_first_source_cannot_be_reached_the_second_is_used() -> None:
    """R-IN-03: a second source is tried when the first one fails."""
    setup = Setup()
    setup.tool_box.unreachable.add(f"{FIRST}/ffmpeg.zip")
    setup.service.verify()

    final = setup.install(ToolName.FFMPEG)

    assert final.status is ToolStatus.OK
    assert final.source == "jellyfin-ffmpeg"
    assert setup.tool_box.fetched == [f"{FIRST}/ffmpeg.zip", f"{SECOND}/both.tar.xz"]


def test_a_tool_from_the_first_source_that_does_not_run_is_replaced_by_the_second() -> None:
    """R-IN-03: whichever file is installed must pass the same self-check."""
    setup = Setup()
    setup.tool_box.downloads[f"{FIRST}/ffprobe.zip"], sha = archive(
        ArchiveKind.ZIP, {"ffprobe": "ffprobe version 9.0.2", "extra": "x"}
    )
    setup.service = ToolchainService(
        specs=(
            ToolSpec(
                ToolName.FFMPEG,
                ("ffmpeg", "ffprobe"),
                ("-version",),
                (
                    ToolSource(
                        "martin-riedl",
                        "9.0.2",
                        {
                            "arm64": (
                                ToolFile(
                                    f"{FIRST}/ffmpeg.zip", FFMPEG_SHA, ArchiveKind.ZIP, ("ffmpeg",)
                                ),
                                ToolFile(f"{FIRST}/ffprobe.zip", sha, ArchiveKind.ZIP, ("extra",)),
                            )
                        },
                    ),
                    specs()[0].sources[1],
                ),
            ),
        ),
        tool_box=setup.tool_box,
        probe=setup.probe,
        meta=setup.meta,
        events=EventBus(),
        clock=setup.clock,
        run_in_background=setup.background.append,
    )
    setup.service.verify()

    with capture_logs() as logs:
        final = setup.install(ToolName.FFMPEG)

    failed = next(line for line in logs if line["event"] == "tool.install.failed")
    assert failed["error_code"] == "TOOL_MISSING"
    assert failed["reason"] == "the self-check failed"
    assert final.source == "jellyfin-ffmpeg"
    assert final.status is ToolStatus.OK


def test_when_every_source_fails_the_tool_says_why_and_can_be_tried_again() -> None:
    """R-IN-03: a failed step offers a retry, with the reason of the failure."""
    setup = Setup()
    setup.tool_box.unreachable.update({f"{FIRST}/ffmpeg.zip", f"{SECOND}/both.tar.xz"})
    setup.service.verify()

    failed = setup.install(ToolName.FFMPEG)
    setup.tool_box.unreachable.clear()
    retried = setup.install(ToolName.FFMPEG)

    assert failed == ToolReport(
        ToolName.FFMPEG,
        ToolStatus.FAILED,
        error_code=ErrorCode.NETWORK_UNREACHABLE,
        installable=True,
    )
    assert setup.tool_box.staging_is_empty(ToolName.FFMPEG)
    assert retried.status is ToolStatus.OK
    assert retried.source == "martin-riedl"


def test_a_full_disk_is_named_as_the_reason() -> None:
    """R-IN-03: a download that cannot be stored fails with its own error code."""
    setup = Setup()
    setup.tool_box.full_disk = True
    setup.service.verify()

    assert setup.install(ToolName.DENO).error_code is ErrorCode.DISK_FULL


def test_an_archive_without_its_program_fails_with_a_code_instead_of_a_crash() -> None:
    """R-IN-03: a wrong archive is a failed step, not an unexpected error."""
    setup = Setup()
    setup.tool_box.downloads[DENO_URL], sha = archive(ArchiveKind.ZIP, {"node": "v26"})
    deno = ToolSpec(
        ToolName.DENO,
        ("deno",),
        ("--version",),
        (
            ToolSource(
                "deno", "2.9.8", {"arm64": (ToolFile(DENO_URL, sha, ArchiveKind.ZIP, ("deno",)),)}
            ),
        ),
    )
    setup.service = ToolchainService(
        specs=(deno,),
        tool_box=setup.tool_box,
        probe=setup.probe,
        meta=setup.meta,
        events=EventBus(),
        clock=setup.clock,
        run_in_background=setup.background.append,
    )
    setup.service.verify()

    assert setup.install(ToolName.DENO).error_code is ErrorCode.TOOL_MISSING


def test_a_processor_without_a_build_fails_with_a_code() -> None:
    """R-IN-03: a tool that has no build for this Mac is a failed step with a reason."""
    setup = Setup(probe=FakeSystemProbe(architecture="x86_64", packages={"yt-dlp": "2026.10.26"}))
    setup.service.verify()

    with capture_logs() as logs:
        final = setup.install(ToolName.DENO)

    assert final.error_code is ErrorCode.TOOL_MISSING
    assert logs[-1]["reason"] == "no build for this processor"
    assert setup.tool_box.fetched == []


def test_only_the_named_source_is_used_when_a_test_asks_for_it() -> None:
    """infra: the automated checks install from each source on its own (D-053)."""
    setup = Setup(only_source="jellyfin-ffmpeg")
    setup.service.verify()

    final = setup.install(ToolName.FFMPEG)

    assert final.source == "jellyfin-ffmpeg"
    assert setup.tool_box.fetched == [f"{SECOND}/both.tar.xz"]


def test_every_installation_is_logged_with_its_source_and_duration() -> None:
    """R-LG-06, R-IN-03: the log says which source a tool came from."""
    setup = Setup()
    setup.service.verify()
    original_fetch = setup.tool_box.fetch

    def slow_fetch(*args: object, **how: object) -> str:
        setup.clock.advance(2.5)
        return original_fetch(*args, **how)  # type: ignore[arg-type]

    setup.tool_box.fetch = slow_fetch  # type: ignore[method-assign]

    with capture_logs() as logs:
        setup.install(ToolName.DENO)

    assert [line["event"] for line in logs] == ["tool.install.started", "tool.install.finished"]
    assert logs[0]["tool"] == "deno"
    assert logs[0]["source"] == "deno"
    assert logs[1]["version"] == "2.9.8"
    assert logs[1]["duration_ms"] == 2500
    assert all(line["msg"] for line in logs)


def test_every_start_checks_the_tools_and_logs_what_it_found() -> None:
    """R-IN-04: on every start the app verifies the tools still work."""
    setup = Setup()
    setup.service.verify()
    setup.install(ToolName.FFMPEG)
    setup.tool_box.refusing.add("ffprobe")

    with capture_logs() as logs:
        reports = setup.service.verify()

    by_tool = {line["tool"]: line for line in logs if line["event"] == "tool.check"}
    assert setup.report(ToolName.FFMPEG) == ToolReport(
        ToolName.FFMPEG, ToolStatus.BROKEN, version="9.0.2", source="martin-riedl", installable=True
    )
    assert [report.status for report in reports][2:] == [ToolStatus.BROKEN, ToolStatus.MISSING]
    assert by_tool["ffmpeg"]["status"] == "broken"
    assert by_tool["ffmpeg"]["source"] == "martin-riedl"
    assert by_tool["python"]["status"] == "ok"
    assert len(by_tool) == 4


def test_setup_completes_when_the_last_tool_is_installed_and_is_remembered() -> None:
    """R-IN-03: the first-run screen is shown until setup has completed once."""
    setup = Setup()
    setup.service.verify()

    setup.install(ToolName.FFMPEG)
    after_one = (setup.service.setup_required(), setup.meta.get(SETUP_COMPLETED_KEY))
    setup.install(ToolName.DENO)

    assert after_one == (True, None)
    assert setup.service.setup_required() is False
    assert setup.meta.get(SETUP_COMPLETED_KEY) == str(int(setup.clock.now().timestamp()))


def test_a_later_start_with_one_tool_gone_needs_no_first_run_screen() -> None:
    """R-IN-04: one missing tool after setup gets the banner, not the first-run screen."""
    setup = Setup()
    setup.service.verify()
    setup.install(ToolName.FFMPEG)
    setup.install(ToolName.DENO)
    completed_at = setup.meta.get(SETUP_COMPLETED_KEY)
    setup.tool_box.lose(ToolName.DENO, "deno")
    setup.clock.advance(3600)

    setup.service.verify()

    assert setup.report(ToolName.DENO).status is ToolStatus.BROKEN
    assert setup.service.setup_required() is False
    assert setup.meta.get(SETUP_COMPLETED_KEY) == completed_at


def test_a_later_start_with_two_tools_gone_shows_the_first_run_screen_again() -> None:
    """R-IN-03: the first-run screen comes back when two or more tools are missing."""
    setup = Setup()
    setup.service.verify()
    setup.install(ToolName.FFMPEG)
    setup.install(ToolName.DENO)
    setup.tool_box.lose(ToolName.DENO, "deno")
    setup.tool_box.lose(ToolName.FFMPEG, "ffprobe")

    setup.service.verify()

    assert setup.service.setup_required() is True
    setup.install(ToolName.DENO)
    assert setup.service.setup_required() is True
    setup.install(ToolName.FFMPEG)
    assert setup.service.setup_required() is False


def test_tools_that_are_all_there_at_the_very_first_start_need_no_setup() -> None:
    """R-IN-03: with nothing to install, the first-run screen has nothing to show."""
    setup = Setup()
    setup.service.verify()
    setup.install(ToolName.FFMPEG)
    setup.install(ToolName.DENO)
    setup.meta.facts.clear()

    setup.service.verify()

    assert setup.service.setup_required() is False
    assert setup.meta.get(SETUP_COMPLETED_KEY) is not None


def test_before_the_first_check_nothing_is_known_and_setup_counts_as_needed() -> None:
    """R-IN-03: the interface never sees "all in order" before the tools were checked."""
    setup = Setup()

    assert setup.service.reports() == ()
    assert setup.service.setup_required() is True
