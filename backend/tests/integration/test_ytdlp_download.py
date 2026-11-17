"""Tests of the download of the yt-dlp gateway, with recorded metadata and a stand-in for yt-dlp.

The options are those verified with a real download in milestone M3 (Q-04,
ARCHITECTURE section 7.3). The live test downloads a real video.
"""

import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from tests.fixtures.fakes.clock import FakeClock
from tests.fixtures.ytdlp_replay import VIDEO_ID, Replay
from ytmirror.adapters.ytdlp_gateway import FRESH_INFO_S, TAGS_STEP, GatewayTools, YtDlpGateway
from ytmirror.core.channels import Quality
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.core.jobs import (
    DownloadCancelledError,
    DownloadProgress,
    DownloadRequest,
    Stage,
    SubtitleKind,
    SubtitlesFailedError,
)

TOOLS = GatewayTools(ffmpeg_folder=Path("/app/tools/ffmpeg"), deno=Path("/app/tools/deno/deno"))
UPLOADED = 1_114_313_512
"""The upload time in the recording: 2005-04-24 03:31:52 UTC."""


class FakeYtDlp:
    """Stands in for a download with yt-dlp: writes the files and calls the hooks.

    Attributes:
        options: The options of the last download.
        tags: The tags of the last download.
        fail: An error to raise at a processing step, as (step, error), or None.
        write_mkv: Whether the merged file is written.
        video_size: The size YouTube gives for the video stream, or None.
        audio_size: The size YouTube gives for the audio stream, or None.
        extra: More fields of the metadata yt-dlp gives back.
    """

    def __init__(self) -> None:
        """Download nothing yet."""
        self.options: Mapping[str, Any] = {}
        self.tags: Mapping[str, str] = {}
        self.fail: tuple[str, Exception] | None = None
        self.write_mkv = True
        self.video_size: int | None = 3000
        self.audio_size: int | None = 1000
        self.extra: dict[str, Any] = {}
        self.calls = 0
        self.refuse_links = 0
        """How many downloads YouTube answers with HTTP 403, as for links that expired."""

    def __call__(
        self, info: Mapping[str, Any], options: Mapping[str, Any], tags: Mapping[str, str]
    ) -> Mapping[str, Any]:
        """Do what yt-dlp does, in the order the real download showed."""
        self.options = options
        self.tags = tags
        self.info = info
        self.calls += 1
        if self.refuse_links > 0:
            self.refuse_links -= 1
            raise RuntimeError("ERROR: unable to download video data: HTTP Error 403: Forbidden")
        address = f"https://www.youtube.com/watch?v={info.get('id')}"
        folder = Path(options["outtmpl"]["default"]).parent
        progress: Callable[[Mapping[str, Any]], None] = options["progress_hooks"][0]
        processing: Callable[[Mapping[str, Any]], None] = options["postprocessor_hooks"][0]
        options["logger"].info(f"[youtube] Extracting URL: {address}")
        # The step that adds the tags of the app runs before the download, and
        # yt-dlp calls the hook for it too (test_ytdlp_real_download.py).
        # Before the download (seen with the real yt-dlp): the tags step, then the
        # conversion of the thumbnail, then the subtitle file, which has no codec.
        for step in (TAGS_STEP, "FFmpegThumbnailsConvertor"):
            processing({"status": "started", "postprocessor": step})
            processing({"status": "finished", "postprocessor": step})
        (folder / f"{VIDEO_ID}.jpg").write_bytes(b"jpeg")
        subtitle = {"ext": "vtt", "url": "https://example.invalid/en.vtt"}
        progress({"status": "downloading", "info_dict": subtitle, "downloaded_bytes": 10})
        progress({"status": "finished", "info_dict": subtitle, "downloaded_bytes": 10})
        video = {"vcodec": "av01", "acodec": "none", "height": 480, "format_id": "397"}
        audio = {"vcodec": "none", "acodec": "opus", "format_id": "251"}
        sizes = {"397": self.video_size, "251": self.audio_size}
        for stream in (video, audio):
            format_id = str(stream["format_id"])
            total = sizes[format_id] or 1000
            for done in (total // 2, total):
                progress(
                    {
                        "status": "downloading",
                        "info_dict": stream,
                        "downloaded_bytes": done,
                        "total_bytes": sizes[format_id],
                        "speed": 2048.0,
                        "eta": 3,
                    }
                )
            progress(
                {
                    "status": "finished",
                    "info_dict": stream,
                    "downloaded_bytes": total,
                    "total_bytes": total,
                }
            )
        for step in ("Merger", "EmbedSubtitle", "Metadata", "EmbedThumbnail", "MoveFiles"):
            processing({"status": "started", "postprocessor": step})
            if self.fail is not None and self.fail[0] == step:
                raise self.fail[1]
            if step == "Merger" and self.write_mkv:
                (folder / f"{VIDEO_ID}.mkv").write_bytes(b"mkv")
            processing({"status": "finished", "postprocessor": step})
        return {
            "id": VIDEO_ID,
            "title": "A recorded video",
            "duration": 19,
            "height": 480,
            **self.extra,
        }


@pytest.fixture
def ytdlp() -> FakeYtDlp:
    """The stand-in for a download with yt-dlp."""
    return FakeYtDlp()


@pytest.fixture
def replay(ytdlp: FakeYtDlp) -> Replay:
    """The recorded metadata of a video, and of channels.

    The lookup before a download is made with the format choice of the download,
    so it names the streams yt-dlp will fetch, with the sizes YouTube gives (D-088).
    """
    replay = Replay()
    replay.video["requested_formats"] = [
        {"format_id": "397", "vcodec": "av01", "acodec": "none", "filesize": ytdlp.video_size},
        {"format_id": "251", "vcodec": "none", "acodec": "opus", "filesize": ytdlp.audio_size},
    ]
    return replay


def gateway(replay: Replay, ytdlp: FakeYtDlp) -> YtDlpGateway:
    """Return the real gateway with stand-ins for yt-dlp."""
    return YtDlpGateway(FakeClock(), tools=TOOLS, extract=replay, download=ytdlp)


def request(tmp_path: Path, **changes: Any) -> DownloadRequest:
    """Return a download of the recorded video into a temp folder of a job."""
    work = tmp_path / ".yt-mirror" / "tmp" / "01JOB"
    work.mkdir(parents=True, exist_ok=True)
    values: dict[str, Any] = {
        "video_id": VIDEO_ID,
        "quality": Quality.P480,
        "work_folder": work,
        "log_file": tmp_path / "logs" / "jobs" / "01JOB.log",
        **changes,
    }
    return DownloadRequest(**values)


def never() -> bool:
    """Is never cancelled."""
    return False


def test_the_download_uses_the_verified_options_and_the_tools_of_the_app_folder(
    tmp_path: Path, replay: Replay, ytdlp: FakeYtDlp
) -> None:
    """R-QL-01, R-QL-03, R-QL-04, R-PL-15: the selector, MKV, no re-encoding, the app's tools."""
    gateway(replay, ytdlp).download(request(tmp_path), lambda _progress: None, never)

    options = ytdlp.options
    assert options["format"] == "bv*[height<=480]+ba/b[height<=480]/wv*+ba/w"
    assert options["merge_output_format"] == "mkv"
    assert options["outtmpl"] == {"default": str(request(tmp_path).work_folder / "%(id)s.%(ext)s")}
    assert options["ffmpeg_location"] == "/app/tools/ffmpeg"
    assert options["js_runtimes"] == {"deno": {"path": "/app/tools/deno/deno"}}
    assert "remote_components" not in options
    assert options["cachedir"] is False
    assert "updatetime" not in options
    assert [step["key"] for step in options["postprocessors"]] == [
        "FFmpegThumbnailsConvertor",
        "FFmpegEmbedSubtitle",
        "FFmpegMetadata",
        "EmbedThumbnail",
    ]
    assert not any(
        "Convertor" in step["key"] and "Video" in step["key"] for step in options["postprocessors"]
    )


def test_the_metadata_step_adds_chapters_and_the_info_json(
    tmp_path: Path, replay: Replay, ytdlp: FakeYtDlp
) -> None:
    """R-MD-01, R-MD-02: chapters, metadata and the raw info JSON go into the file."""
    gateway(replay, ytdlp).download(request(tmp_path), lambda _progress: None, never)

    metadata = next(
        step for step in ytdlp.options["postprocessors"] if step["key"] == "FFmpegMetadata"
    )
    assert metadata == {
        "key": "FFmpegMetadata",
        "add_chapters": True,
        "add_metadata": True,
        "add_infojson": True,
    }


def test_the_exact_published_time_and_the_video_id_are_tags_of_the_file(
    tmp_path: Path, replay: Replay, ytdlp: FakeYtDlp
) -> None:
    """R-MD-01, R-DT-08: the published time to the second and the video ID are embedded."""
    gateway(replay, ytdlp).download(request(tmp_path), lambda _progress: None, never)

    assert ytdlp.tags == {"video_id": VIDEO_ID, "published_at": "2005-04-24T03:31:52Z"}


def test_a_premiere_is_tagged_with_its_release_time(tmp_path: Path, ytdlp: FakeYtDlp) -> None:
    """R-DT-03, R-DT-08: a premiere's published time is the release time, not the upload."""
    replay = Replay()
    replay.video = {**replay.video, "release_timestamp": UPLOADED + 3600}

    result = gateway(replay, ytdlp).download(request(tmp_path), lambda _progress: None, never)

    assert ytdlp.tags["published_at"] == "2005-04-24T04:31:52Z"
    assert (result.release_time, result.upload_time) == (UPLOADED + 3600, UPLOADED)


def test_a_premiere_that_is_not_public_yet_is_not_downloaded(
    tmp_path: Path, ytdlp: FakeYtDlp
) -> None:
    """R-DT-03: a scheduled video is not available yet, and nothing is downloaded."""
    replay = Replay()
    replay.video = {**replay.video, "live_status": "is_upcoming"}

    with pytest.raises(AppError) as failure:
        gateway(replay, ytdlp).download(request(tmp_path), lambda _progress: None, never)

    assert failure.value.code is ErrorCode.NOT_YET_AVAILABLE
    assert ytdlp.options == {}


def test_creator_subtitles_in_english_are_chosen_first(
    tmp_path: Path, replay: Replay, ytdlp: FakeYtDlp
) -> None:
    """R-MD-03: English subtitles of the creator are embedded when they exist."""
    result = gateway(replay, ytdlp).download(request(tmp_path), lambda _progress: None, never)

    assert (ytdlp.options["writesubtitles"], ytdlp.options["writeautomaticsub"]) == (True, False)
    assert ytdlp.options["subtitleslangs"] == ["en"]
    assert result.subtitles is SubtitleKind.MANUAL


def test_auto_generated_subtitles_are_the_fallback(tmp_path: Path, ytdlp: FakeYtDlp) -> None:
    """R-MD-03: without creator subtitles in English, the auto-generated ones are embedded."""
    replay = Replay()
    replay.video = {**replay.video, "subtitles": {"de": [{"ext": "vtt"}]}}

    result = gateway(replay, ytdlp).download(request(tmp_path), lambda _progress: None, never)

    assert (ytdlp.options["writesubtitles"], ytdlp.options["writeautomaticsub"]) == (False, True)
    assert result.subtitles is SubtitleKind.AUTO


def test_the_auto_generated_fallback_can_be_switched_off(tmp_path: Path, ytdlp: FakeYtDlp) -> None:
    """R-MD-03: with the fallback setting off, a video without creator subtitles has none."""
    replay = Replay()
    replay.video = {**replay.video, "subtitles": {}}

    result = gateway(replay, ytdlp).download(
        request(tmp_path, auto_subtitles=False), lambda _progress: None, never
    )

    assert result.subtitles is None
    assert "FFmpegEmbedSubtitle" not in [step["key"] for step in ytdlp.options["postprocessors"]]


def test_with_subtitles_switched_off_none_are_embedded(
    tmp_path: Path, replay: Replay, ytdlp: FakeYtDlp
) -> None:
    """R-MD-03: with the subtitle setting off, nothing is asked for, not even the fallback."""
    result = gateway(replay, ytdlp).download(
        request(tmp_path, manual_subtitles=False), lambda _progress: None, never
    )

    assert result.subtitles is None
    assert ytdlp.options["writesubtitles"] is False
    assert ytdlp.options["writeautomaticsub"] is False


def test_progress_goes_from_0_to_100_percent_once_for_the_whole_mirror(
    tmp_path: Path, replay: Replay, ytdlp: FakeYtDlp
) -> None:
    """R-QU-04, D-088: video and audio, each reported from 0 to 100% by yt-dlp, count as one.

    The reports have the shape of the real yt-dlp: the information of each stream
    names no other stream. The M3 test gave them ``requested_formats``, which hid
    that the second stream started again at 0%.
    """
    told: list[DownloadProgress] = []

    gateway(replay, ytdlp).download(request(tmp_path), told.append, never)

    downloading = [report for report in told if report.stage is not Stage.PROCESSING]
    fractions = [report.fraction or 0.0 for report in downloading]
    assert fractions == sorted(fractions)
    assert fractions[-1] == 1.0
    assert fractions.count(1.0) == 1
    assert told[-1].stage is Stage.PROCESSING or told.index(
        DownloadProgress(stage=Stage.PROCESSING)
    ) == len(downloading)
    last = downloading[-1]
    assert last.total_bytes == last.downloaded_bytes
    assert {part.kind.value for part in last.parts} == {"thumbnail", "subtitles", "video", "audio"}
    assert all(part.finished for part in last.parts)
    audio_starts = next(report for report in downloading if report.stage is Stage.AUDIO)
    video_ends = downloading[downloading.index(audio_starts) - 1]
    assert (audio_starts.fraction or 0) >= (video_ends.fraction or 0)


def test_a_stream_without_a_size_is_estimated_and_the_percent_never_goes_down(
    tmp_path: Path, replay: Replay, ytdlp: FakeYtDlp
) -> None:
    """R-QU-04, D-088: an unknown size is estimated, corrected, and the percent only grows."""
    ytdlp.audio_size = None
    replay.video["requested_formats"][1]["filesize"] = None
    told: list[DownloadProgress] = []

    gateway(replay, ytdlp).download(request(tmp_path), told.append, never)

    downloading = [report for report in told if report.stage is not Stage.PROCESSING]
    fractions = [report.fraction or 0.0 for report in downloading]
    assert fractions == sorted(fractions)
    assert fractions[-1] == 1.0
    first = downloading[0]
    audio = next(part for part in first.parts if part.kind.value == "audio")
    assert audio.estimated


def test_a_finished_download_gives_its_file_thumbnail_metadata_and_chapters(
    tmp_path: Path, replay: Replay, ytdlp: FakeYtDlp
) -> None:
    """R-MD-02, R-MD-05, R-UI-08: the file, the original thumbnail and the raw JSON come back."""
    asked = request(tmp_path)

    result = gateway(replay, ytdlp).download(asked, lambda _progress: None, never)

    assert result.file == asked.work_folder / f"{VIDEO_ID}.mkv"
    assert result.thumbnail == asked.work_folder / f"{VIDEO_ID}.jpg"
    assert json.loads(result.info_json)["id"] == VIDEO_ID
    assert (result.title, result.duration_s) == ("A recorded video", 19)
    assert [chapter.title for chapter in result.chapters] == ["Chapter 1", "Chapter 2", "Chapter 3"]


def test_the_raw_metadata_can_always_be_written_as_utf_8(
    tmp_path: Path, replay: Replay, ytdlp: FakeYtDlp
) -> None:
    """R-MD-02, R-QA-06: a lone surrogate from YouTube is kept, escaped, and breaks no write."""
    ytdlp.extra = {"description": "half an emoji \ud83d and caf\u00e9"}

    result = gateway(replay, ytdlp).download(request(tmp_path), lambda _progress: None, never)

    assert json.loads(result.info_json.encode("utf-8"))["description"] == (
        "half an emoji \ud83d and caf\u00e9"
    )


def test_readable_metadata_stays_readable(tmp_path: Path, replay: Replay, ytdlp: FakeYtDlp) -> None:
    """R-MD-02: text without a lone surrogate is kept as it is, not escaped."""
    ytdlp.extra = {"description": "caf\u00e9"}

    result = gateway(replay, ytdlp).download(request(tmp_path), lambda _progress: None, never)

    assert "caf\u00e9" in result.info_json


def test_everything_yt_dlp_says_goes_into_the_log_of_the_job(
    tmp_path: Path, replay: Replay, ytdlp: FakeYtDlp
) -> None:
    """R-LG-02: the output of yt-dlp of one download is in the log file of its job."""
    asked = request(tmp_path)

    gateway(replay, ytdlp).download(asked, lambda _progress: None, never)

    assert "[youtube] Extracting URL" in asked.log_file.read_text(encoding="utf-8")


def test_a_cancel_while_bytes_arrive_ends_the_download(
    tmp_path: Path, replay: Replay, ytdlp: FakeYtDlp
) -> None:
    """R-QU-02: Cancel ends a download while it downloads."""
    told: list[DownloadProgress] = []

    with pytest.raises(DownloadCancelledError):
        gateway(replay, ytdlp).download(request(tmp_path), told.append, lambda: len(told) >= 1)

    assert len(told) == 1


def test_a_cancel_during_processing_ends_the_download_at_the_next_step(
    tmp_path: Path, replay: Replay, ytdlp: FakeYtDlp
) -> None:
    """R-QU-02: Cancel also works while the file is merged and its metadata embedded."""
    told: list[DownloadProgress] = []

    def cancelled() -> bool:
        return any(report.stage is Stage.PROCESSING for report in told)

    with pytest.raises(DownloadCancelledError, match="Merger"):
        gateway(replay, ytdlp).download(request(tmp_path), told.append, cancelled)


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("x: Join this channel to get access to members-only content", ErrorCode.MEMBERS_ONLY),
        ("x: Private video. Sign in if you've been granted access", ErrorCode.VIDEO_PRIVATE),
        ("x: Video unavailable. This video has been removed", ErrorCode.VIDEO_REMOVED),
        ("x: Sign in to confirm your age", ErrorCode.AGE_RESTRICTED),
        (
            "x: The uploader has not made this video available in your country",
            ErrorCode.GEO_BLOCKED,
        ),
        ("x: Premieres in 3 hours", ErrorCode.NOT_YET_AVAILABLE),
        ("x: Requested format is not available", ErrorCode.NO_FORMATS),
        ("unable to download video data: HTTP Error 404: Not Found", ErrorCode.VIDEO_REMOVED),
        ("unable to download video data: HTTP Error 429", ErrorCode.RATE_LIMITED),
        ("x: Sign in to confirm you\u2019re not a bot", ErrorCode.BOT_CHECK),
        ("unable to write data: [Errno 28] No space left on device", ErrorCode.DISK_FULL),
        ("ERROR: Postprocessing: Conversion failed!", ErrorCode.FFMPEG_FAILED),
        ("x: Read timed out", ErrorCode.NETWORK_UNREACHABLE),
        ("something nobody has seen before", ErrorCode.YOUTUBE_CHANGED),
    ],
)
def test_the_errors_of_a_download_get_their_codes(
    tmp_path: Path, replay: Replay, ytdlp: FakeYtDlp, text: str, code: ErrorCode
) -> None:
    """R-ER-02: every error of a download has a code, and its full text is kept."""
    ytdlp.fail = ("Merger", RuntimeError(text))

    with pytest.raises(AppError) as failure:
        gateway(replay, ytdlp).download(request(tmp_path), lambda _progress: None, never)

    assert failure.value.code is code
    assert failure.value.details["message"] == text


def test_an_error_of_the_metadata_lookup_is_about_the_video(
    tmp_path: Path, ytdlp: FakeYtDlp
) -> None:
    """R-ER-02: a video that is gone is not reported as a channel that is not found."""
    replay = Replay()
    replay.video_error = "[youtube] x: Video unavailable"

    with pytest.raises(AppError) as failure:
        gateway(replay, ytdlp).download(request(tmp_path), lambda _progress: None, never)

    assert failure.value.code is ErrorCode.VIDEO_REMOVED


def test_a_failure_of_the_subtitles_is_told_apart(
    tmp_path: Path, replay: Replay, ytdlp: FakeYtDlp
) -> None:
    """R-MD-04: when the subtitles fail, the caller can try once more without them."""
    ytdlp.fail = ("EmbedSubtitle", RuntimeError("ERROR: Postprocessing: Conversion failed!"))

    with pytest.raises(SubtitlesFailedError):
        gateway(replay, ytdlp).download(request(tmp_path), lambda _progress: None, never)


def test_a_subtitle_download_error_is_told_apart(
    tmp_path: Path, replay: Replay, ytdlp: FakeYtDlp
) -> None:
    """R-MD-04: yt-dlp's "Unable to download video subtitles" is a failure of the subtitles."""
    ytdlp.fail = ("Merger", RuntimeError("ERROR: Unable to download video subtitles for 'en'"))

    with pytest.raises(SubtitlesFailedError):
        gateway(replay, ytdlp).download(request(tmp_path), lambda _progress: None, never)


def test_a_download_without_a_merged_file_failed(
    tmp_path: Path, replay: Replay, ytdlp: FakeYtDlp
) -> None:
    """R-QA-06: yt-dlp ending without an MKV file is a failure, never a finished video."""
    ytdlp.write_mkv = False

    with pytest.raises(AppError) as failure:
        gateway(replay, ytdlp).download(request(tmp_path), lambda _progress: None, never)

    assert failure.value.code is ErrorCode.FFMPEG_FAILED


@pytest.mark.parametrize("step", ["Merger", "EmbedSubtitle"])
def test_an_error_after_a_cancel_is_the_cancel(
    tmp_path: Path, replay: Replay, ytdlp: FakeYtDlp, step: str
) -> None:
    """R-QU-02, R-PL-13: when ffmpeg was stopped by a cancel or a quit, its error is the cancel.

    Never a failure with a code, and never a failure of the subtitles that is tried again.
    """
    cancelled = {"now": False}
    ytdlp.fail = (step, RuntimeError("ERROR: Postprocessing: Conversion failed!"))
    # The cancel arrives as the failing step starts: no later hook can see it first.
    at = ["Merger", "EmbedSubtitle"].index(step) + 1
    processing: list[DownloadProgress] = []

    def cancel_when_processing(report: DownloadProgress) -> None:
        if report.stage is Stage.PROCESSING:
            processing.append(report)
            cancelled["now"] = len(processing) == at

    with pytest.raises(DownloadCancelledError):
        gateway(replay, ytdlp).download(
            request(tmp_path), cancel_when_processing, lambda: cancelled["now"]
        )


def test_a_download_asks_youtube_once_and_downloads_what_the_lookup_gave(
    tmp_path: Path, replay: Replay, ytdlp: FakeYtDlp
) -> None:
    """R-DT-06, D-088: one lookup per download, counted once in the budget.

    The download is made from the metadata the lookup gave, with the format choice
    of the download, so the streams fetched are those the progress was planned with.
    """
    asked: list[str] = []

    def counting(address: str, options: Mapping[str, Any], process: bool) -> Mapping[str, Any]:
        asked.append(address)
        return replay(address, options, process)

    YtDlpGateway(FakeClock(), tools=TOOLS, extract=counting, download=ytdlp).download(
        request(tmp_path), lambda _progress: None, never
    )

    assert asked == [f"https://www.youtube.com/watch?v={VIDEO_ID}"]
    assert ytdlp.info["id"] == VIDEO_ID
    assert [stream["format_id"] for stream in ytdlp.info["requested_formats"]] == ["397", "251"]


def counting(replay: Replay, asked: list[str]) -> Any:
    """The replay of yt-dlp, noting every address it is asked."""

    def extract(address: str, options: Mapping[str, Any], process: bool) -> Mapping[str, Any]:
        asked.append(address)
        return replay(address, options, process)

    return extract


def test_links_youtube_refuses_are_read_again_once_and_counted(
    tmp_path: Path, replay: Replay, ytdlp: FakeYtDlp
) -> None:
    """R-DT-06, D-088: an HTTP 403 on reused metadata: one more lookup, counted, then a retry."""
    asked: list[str] = []
    again: list[int] = []
    ytdlp.refuse_links = 1
    gateway = YtDlpGateway(
        FakeClock(), tools=TOOLS, extract=counting(replay, asked), download=ytdlp
    )

    result = gateway.download(
        request(tmp_path), lambda _p: None, never, on_lookup_again=lambda: again.append(1)
    )

    assert result.file.name == f"{VIDEO_ID}.mkv"
    assert (len(asked), len(again), ytdlp.calls) == (2, 1, 2)


def test_links_refused_twice_are_not_read_a_third_time(
    tmp_path: Path, replay: Replay, ytdlp: FakeYtDlp
) -> None:
    """R-DT-06: one retry only; the second refusal fails the download with its code."""
    asked: list[str] = []
    ytdlp.refuse_links = 2
    gateway = YtDlpGateway(
        FakeClock(), tools=TOOLS, extract=counting(replay, asked), download=ytdlp
    )

    with pytest.raises(AppError):
        gateway.download(request(tmp_path), lambda _p: None, never)

    assert (len(asked), ytdlp.calls) == (2, 2)


def test_metadata_older_than_five_minutes_is_read_again_before_the_download(
    tmp_path: Path, replay: Replay, ytdlp: FakeYtDlp
) -> None:
    """R-DT-06: old metadata may hold expired links: one more lookup, counted."""
    asked: list[str] = []
    again: list[int] = []
    clock = FakeClock()
    gateway = YtDlpGateway(clock, tools=TOOLS, extract=counting(replay, asked), download=ytdlp)

    gateway.download(
        request(tmp_path),
        lambda _p: None,
        never,
        start_writing=lambda: clock.advance(FRESH_INFO_S + 1),
        on_lookup_again=lambda: again.append(1),
    )

    assert (len(asked), len(again), ytdlp.calls) == (2, 1, 1)
