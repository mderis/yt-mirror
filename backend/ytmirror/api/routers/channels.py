"""The channel endpoints: look up, add, change, remove, check, open the folder.

Implements the HTTP side of R-CH-01 to R-CH-06, R-CH-23, R-CH-27 and
R-CH-30 to R-CH-32. No logic here: the services decide.

Tests: backend/tests/api/test_channels.py
"""

from fastapi import APIRouter
from starlette.responses import Response

from ytmirror.api.catalogue_schemas import (
    AddChannelRequest,
    AddChannelResponse,
    AutoMirrorAnswerRequest,
    AutoMirrorRequest,
    CancelCheckResponse,
    ChangeChannelRequest,
    Channel,
    CheckAllResponse,
    CheckRequest,
    ChosenFolderResponse,
    FilesToTrashResponse,
    KeptFileResponse,
    LookupRequest,
    LookupResponse,
    MirrorResponse,
    QueuedJob,
    RemovedChannelResponse,
    RepairDatesResponse,
    VideoCountResponse,
)
from ytmirror.api.pictures import picture_response
from ytmirror.core.errors import AppError, ErrorCode
from ytmirror.services.auto_mirror import AutoMirrorService
from ytmirror.services.catalogue import CatalogueService
from ytmirror.services.channel_views import ChannelViews
from ytmirror.services.channels import ChannelsService, NewChannel
from ytmirror.services.repair import RepairService
from ytmirror.services.thumbnails import ThumbnailService

_CREATED = 201
_ACCEPTED = 202
_NO_CONTENT = 204


def build_router(
    channels: ChannelsService,
    catalogue: CatalogueService,
    views: ChannelViews,
    thumbnails: ThumbnailService,
    repair: RepairService | None = None,
    auto_mirror: AutoMirrorService | None = None,
) -> APIRouter:
    """Return the router for ``/channels`` and ``/folders``.

    Args:
        channels: The use cases around one channel.
        catalogue: Runs the checks.
        views: The channels as the interface shows them.
        thumbnails: The cached pictures.
        repair: Repairs the dates of a channel's files on demand (R-DT-09).
        auto_mirror: Auto-mirror and "Mirror everything missing" (R-MI-02, R-MI-04).

    Returns:
        The router, to be mounted under ``/api``.
    """
    router = APIRouter(tags=["channels"])

    def view_of(channel_id: str) -> Channel:
        view = views.of(channel_id)
        if view is None:
            raise AppError(ErrorCode.NOT_FOUND, {"channel": channel_id})
        return Channel.of(view)

    def look_up_channel(body: LookupRequest) -> LookupResponse:
        """Resolve what the user pasted to the preview of a channel (R-CH-03)."""
        return LookupResponse.of(channels.lookup(body.text))

    def get_video_count(channel_id: str) -> VideoCountResponse:
        """Return the video count of a preview, or none when YouTube gave none in time."""
        return VideoCountResponse(video_count=channels.video_count(channel_id))

    def get_preview_avatar(channel_id: str) -> Response:
        """Return the avatar of a channel that was looked up, for its preview."""
        return picture_response(channels.preview_avatar(channel_id), "the avatar of the preview")

    def choose_folder() -> ChosenFolderResponse:
        """Show the folder dialog of macOS and return what the user chose (R-CH-05)."""
        return ChosenFolderResponse.of(channels.choose_folder())

    def add_channel(body: AddChannelRequest, response: Response) -> AddChannelResponse:
        """Add a channel that was looked up, and start its first listing (R-CH-05)."""
        added = channels.add(
            NewChannel(
                channel_id=body.channel_id,
                folder=body.folder,
                quality=body.quality,
                auto_mirror=body.auto_mirror,
                mirror_after=body.mirror_after,
            )
        )
        if added.existing:
            response.status_code = 200
        return AddChannelResponse(channel=Channel.of(added.view), existing=added.existing)

    def get_channel(channel_id: str) -> Channel:
        """Return one channel as the interface shows it."""
        return view_of(channel_id)

    def change_channel(channel_id: str, body: ChangeChannelRequest) -> Channel:
        """Pause or resume a channel (R-CH-31)."""
        return Channel.of(channels.set_paused(channel_id, body.paused))

    def remove_channel(channel_id: str, keep_files: bool = True) -> RemovedChannelResponse:
        """Remove a channel with its catalogue, and its files or not (R-CH-32).

        The answer lists every file that stayed, with its reason.
        """
        removed = channels.remove(channel_id, keep_files=keep_files)
        return RemovedChannelResponse(
            folder=removed.folder,
            files_trashed=removed.files_trashed,
            left=[KeptFileResponse.of(kept) for kept in removed.left],
        )

    def files_to_trash(channel_id: str) -> FilesToTrashResponse:
        """Say how many files and how much room "Delete the files" moves to the Trash (R-CH-32)."""
        found = channels.files_to_trash(channel_id)
        return FilesToTrashResponse(files=found.files, size_bytes=found.size_bytes)

    def check_channel(channel_id: str, body: CheckRequest | None = None) -> Channel:
        """Start a quick or a full check of a channel (R-CH-23)."""
        asked = body or CheckRequest()
        catalogue.request_check(channel_id, asked.kind, trigger=asked.trigger)
        return view_of(channel_id)

    def repair_dates(channel_id: str) -> RepairDatesResponse:
        """Compare the dates of a channel's synced files and repair them (R-DT-09)."""
        if repair is None:
            raise AppError(ErrorCode.NOT_FOUND, {"channel": channel_id})
        result = repair.repair_dates(channel_id)
        return RepairDatesResponse(
            checked=result.checked, repaired=result.repaired, failed=result.failed
        )

    def cancel_check(channel_id: str) -> CancelCheckResponse:
        """Cancel the full check of a channel that waits or runs (R-CH-27)."""
        if views.of(channel_id) is None:
            raise AppError(ErrorCode.NOT_FOUND, {"channel": channel_id})
        return CancelCheckResponse(cancelled=catalogue.cancel(channel_id))

    def check_all_channels() -> CheckAllResponse:
        """Start a quick check of every channel that is not paused (R-CH-23)."""
        return CheckAllResponse(channels=catalogue.request_check_all())

    def open_channel_folder(channel_id: str) -> Response:
        """Show the folder of a channel in Finder (R-CH-30)."""
        channels.open_folder(channel_id)
        return Response(status_code=_NO_CONTENT)

    def get_avatar(channel_id: str) -> Response:
        """Return the cached avatar of a channel (R-CH-16)."""
        return picture_response(thumbnails.avatar(channel_id), "the avatar of this channel")

    add = router.add_api_route
    add(
        "/channels/lookup",
        look_up_channel,
        methods=["POST"],
        response_model=LookupResponse,
        operation_id="lookUpChannel",
    )
    add(
        "/channels/lookup/{channel_id}/video-count",
        get_video_count,
        methods=["GET"],
        response_model=VideoCountResponse,
        operation_id="getPreviewVideoCount",
    )
    add(
        "/channels/lookup/{channel_id}/avatar",
        get_preview_avatar,
        methods=["GET"],
        response_class=Response,
        operation_id="getPreviewAvatar",
    )
    add(
        "/folders/choose",
        choose_folder,
        methods=["POST"],
        response_model=ChosenFolderResponse,
        operation_id="chooseFolder",
    )
    add(
        "/channels/check-all",
        check_all_channels,
        methods=["POST"],
        response_model=CheckAllResponse,
        status_code=_ACCEPTED,
        operation_id="checkAllChannels",
    )
    add(
        "/channels",
        add_channel,
        methods=["POST"],
        response_model=AddChannelResponse,
        status_code=_CREATED,
        operation_id="addChannel",
    )
    add(
        "/channels/{channel_id}",
        get_channel,
        methods=["GET"],
        response_model=Channel,
        operation_id="getChannel",
    )
    add(
        "/channels/{channel_id}",
        change_channel,
        methods=["PATCH"],
        response_model=Channel,
        operation_id="changeChannel",
    )
    add(
        "/channels/{channel_id}",
        remove_channel,
        methods=["DELETE"],
        response_model=RemovedChannelResponse,
        operation_id="removeChannel",
    )
    add(
        "/channels/{channel_id}/files-to-trash",
        files_to_trash,
        methods=["GET"],
        response_model=FilesToTrashResponse,
        operation_id="getFilesToTrash",
    )
    add(
        "/channels/{channel_id}/check",
        check_channel,
        methods=["POST"],
        response_model=Channel,
        status_code=_ACCEPTED,
        operation_id="checkChannel",
    )
    add(
        "/channels/{channel_id}/repair-dates",
        repair_dates,
        methods=["POST"],
        response_model=RepairDatesResponse,
        operation_id="repairDates",
    )
    add(
        "/channels/{channel_id}/check/cancel",
        cancel_check,
        methods=["POST"],
        response_model=CancelCheckResponse,
        operation_id="cancelCheck",
    )
    add(
        "/channels/{channel_id}/open-folder",
        open_channel_folder,
        methods=["POST"],
        status_code=_NO_CONTENT,
        response_class=Response,
        operation_id="openChannelFolder",
    )
    add(
        "/channels/{channel_id}/avatar",
        get_avatar,
        methods=["GET"],
        response_class=Response,
        operation_id="getChannelAvatar",
    )

    def mirroring() -> AutoMirrorService:
        if auto_mirror is None:
            raise AppError(ErrorCode.NOT_FOUND, {"reason": "auto-mirror is not wired"})
        return auto_mirror

    def set_auto_mirror(channel_id: str, body: AutoMirrorRequest) -> Channel:
        """Turn auto-mirror of a channel on or off (R-MI-02). On asks before a large start."""
        mirroring().set_auto_mirror(channel_id, on=body.on)
        return view_of(channel_id)

    def answer_auto_mirror(channel_id: str, body: AutoMirrorAnswerRequest) -> Channel:
        """Answer the question before a large start of auto-mirror (D-095)."""
        mirroring().answer(channel_id, body.answer)
        return view_of(channel_id)

    def mirror_missing(channel_id: str) -> MirrorResponse:
        """Queue every video of the channel without a file, once (R-MI-04)."""
        jobs = mirroring().mirror_missing(channel_id)
        return MirrorResponse(
            jobs=[QueuedJob(job_id=job.id, video_id=job.video_id) for job in jobs]
        )

    def leave_missing(channel_id: str) -> Channel:
        """Leave the missing files of the channel missing, until more are missing (D-092)."""
        mirroring().leave_missing(channel_id)
        return view_of(channel_id)

    add(
        "/channels/{channel_id}/auto-mirror",
        set_auto_mirror,
        methods=["PUT"],
        response_model=Channel,
        operation_id="setAutoMirror",
    )
    add(
        "/channels/{channel_id}/auto-mirror/answer",
        answer_auto_mirror,
        methods=["POST"],
        response_model=Channel,
        operation_id="answerAutoMirror",
    )
    add(
        "/channels/{channel_id}/mirror-missing",
        mirror_missing,
        methods=["POST"],
        response_model=MirrorResponse,
        status_code=202,
        operation_id="mirrorMissing",
    )
    add(
        "/channels/{channel_id}/missing/leave",
        leave_missing,
        methods=["POST"],
        response_model=Channel,
        operation_id="leaveMissing",
    )
    return router
